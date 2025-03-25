import os
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get a connection to the database."""
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    conn.autocommit = True
    return conn

def create_clustering_tables():
    """Create tables for storing clustering results."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create schema if it doesn't exist
    cur.execute("CREATE SCHEMA IF NOT EXISTS sanollea;")
    
    # Create customer clusters table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sanollea.CUSTOMER_CLUSTERS (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER,
        cluster_id INTEGER,
        cluster_name VARCHAR(255),
        cluster_description TEXT,
        features JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES sanollea.CUSTOMER(id) ON DELETE CASCADE
    );
    """)
    
    # Create product clusters table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sanollea.PRODUCT_CLUSTERS (
        id SERIAL PRIMARY KEY,
        product_name VARCHAR(255),
        cluster_id INTEGER,
        cluster_name VARCHAR(255),
        cluster_description TEXT,
        features JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    cur.close()
    conn.close()

# Create clustering tables on module import
create_clustering_tables()

def get_customer_data():
    """
    Retrieve customer data from the database for clustering.
    
    Returns:
        Pandas DataFrame with customer data
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get customer purchase data
    cur.execute("""
    SELECT 
        c.id as customer_id,
        c.name as customer_name,
        c.email,
        COUNT(i.id) as total_invoices,
        SUM(i.total) as total_spent,
        AVG(i.total) as average_invoice_amount,
        MAX(i.date) as last_purchase_date,
        COUNT(DISTINCT ii.product) as unique_products_bought
    FROM 
        sanollea.CUSTOMER c
    LEFT JOIN 
        sanollea.INVOICE i ON c.id = i.customer_id
    LEFT JOIN 
        sanollea.INVOICE_ITEM ii ON i.id = ii.invoice_id
    GROUP BY 
        c.id, c.name, c.email
    """)
    
    customers = cur.fetchall()
    cur.close()
    conn.close()
    
    if not customers:
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(customers)
    
    # Calculate days since last purchase
    df['last_purchase_date'] = pd.to_datetime(df['last_purchase_date'])
    today = datetime.now().date()
    df['days_since_last_purchase'] = df['last_purchase_date'].apply(
        lambda x: (today - x.date()).days if pd.notnull(x) else 365
    )
    
    return df

def get_product_data():
    """
    Retrieve product data from the database for clustering.
    
    Returns:
        Pandas DataFrame with product data
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get product purchase data
    cur.execute("""
    SELECT 
        ii.product as product_name,
        COUNT(ii.id) as times_purchased,
        AVG(ii.pricePerUnit) as average_price,
        SUM(ii.quantity) as total_quantity_sold,
        COUNT(DISTINCT i.customer_id) as unique_customers
    FROM 
        sanollea.INVOICE_ITEM ii
    JOIN 
        sanollea.INVOICE i ON ii.invoice_id = i.id
    GROUP BY 
        ii.product
    """)
    
    products = cur.fetchall()
    cur.close()
    conn.close()
    
    if not products:
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(products)
    
    return df

def cluster_customers():
    """
    Cluster customers based on their purchasing behavior.
    
    Returns:
        List of dictionaries with cluster information
    """
    # Get customer data
    df = get_customer_data()
    
    if df.empty:
        return []
    
    # Select features for clustering
    features = [
        'total_invoices', 
        'total_spent', 
        'average_invoice_amount', 
        'days_since_last_purchase',
        'unique_products_bought'
    ]
    
    # Handle missing values
    for feature in features:
        df[feature] = df[feature].fillna(0)
    
    # Extract feature matrix
    X = df[features].values
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Determine optimal number of clusters (simplified)
    n_clusters = min(5, len(df))
    
    # Apply K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    df['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Calculate cluster centers and characteristics
    cluster_centers = scaler.inverse_transform(kmeans.cluster_centers_)
    
    # Define cluster names and descriptions
    cluster_names = {
        0: "High Value",
        1: "Regular",
        2: "Occasional",
        3: "New",
        4: "At Risk"
    }
    
    cluster_descriptions = {
        0: "High spending customers with frequent purchases",
        1: "Regular customers with consistent purchasing patterns",
        2: "Occasional customers who purchase infrequently",
        3: "New customers with recent first purchases",
        4: "Customers at risk of churn with no recent purchases"
    }
    
    # Assign appropriate names based on cluster characteristics
    cluster_mapping = {}
    for i in range(n_clusters):
        center = cluster_centers[i]
        # Determine cluster type based on center values
        if center[1] > df['total_spent'].mean() * 1.5:  # High total spent
            cluster_mapping[i] = 0  # High Value
        elif center[3] < 30 and center[0] <= 2:  # Recent purchase but few invoices
            cluster_mapping[i] = 3  # New
        elif center[3] > 180:  # No purchase in last 6 months
            cluster_mapping[i] = 4  # At Risk
        elif center[0] > df['total_invoices'].mean():  # Above average invoices
            cluster_mapping[i] = 1  # Regular
        else:
            cluster_mapping[i] = 2  # Occasional
    
    # Map original cluster numbers to meaningful ones
    df['cluster_type'] = df['cluster'].map(cluster_mapping)
    
    # Save results to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Clear previous clustering results
    cur.execute("DELETE FROM sanollea.CUSTOMER_CLUSTERS")
    
    # Insert new clustering results
    for _, row in df.iterrows():
        cluster_type = int(row['cluster_type'])
        features_json = {
            'total_invoices': float(row['total_invoices']),
            'total_spent': float(row['total_spent']),
            'average_invoice_amount': float(row['average_invoice_amount']),
            'days_since_last_purchase': float(row['days_since_last_purchase']),
            'unique_products_bought': float(row['unique_products_bought'])
        }
        
        cur.execute("""
        INSERT INTO sanollea.CUSTOMER_CLUSTERS (
            customer_id, cluster_id, cluster_name, cluster_description, features
        )
        VALUES (%s, %s, %s, %s, %s)
        """, (
            row['customer_id'],
            cluster_type,
            cluster_names[cluster_type],
            cluster_descriptions[cluster_type],
            json.dumps(features_json)
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    
    # Prepare results for API response
    clusters = []
    for i in range(5):  # 5 cluster types
        if i in df['cluster_type'].values:
            cluster_customers = df[df['cluster_type'] == i]
            clusters.append({
                'id': i,
                'name': cluster_names[i],
                'description': cluster_descriptions[i],
                'count': len(cluster_customers),
                'avg_spent': cluster_customers['total_spent'].mean(),
                'avg_invoices': cluster_customers['total_invoices'].mean(),
                'customers': cluster_customers['customer_id'].tolist()
            })
    
    return clusters

def cluster_products():
    """
    Cluster products based on their characteristics and purchase patterns.
    
    Returns:
        List of dictionaries with cluster information
    """
    # Get product data
    df = get_product_data()
    
    if df.empty:
        return []
    
    # Select features for clustering
    features = [
        'times_purchased', 
        'average_price', 
        'total_quantity_sold', 
        'unique_customers'
    ]
    
    # Handle missing values
    for feature in features:
        df[feature] = df[feature].fillna(0)
    
    # Extract feature matrix
    X = df[features].values
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Determine optimal number of clusters (simplified)
    n_clusters = min(4, len(df))
    
    # Apply K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    df['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Calculate cluster centers and characteristics
    cluster_centers = scaler.inverse_transform(kmeans.cluster_centers_)
    
    # Define cluster names and descriptions
    cluster_names = {
        0: "Popular",
        1: "Premium",
        2: "Niche",
        3: "Standard"
    }
    
    cluster_descriptions = {
        0: "Frequently purchased products with wide customer base",
        1: "High-priced products with selective customer base",
        2: "Specialized products with limited customer base",
        3: "Standard products with average purchase frequency and price"
    }
    
    # Assign appropriate names based on cluster characteristics
    cluster_mapping = {}
    for i in range(n_clusters):
        center = cluster_centers[i]
        # Determine cluster type based on center values
        if center[0] > df['times_purchased'].mean() * 1.5 and center[3] > df['unique_customers'].mean() * 1.2:
            cluster_mapping[i] = 0  # Popular
        elif center[1] > df['average_price'].mean() * 1.5:
            cluster_mapping[i] = 1  # Premium
        elif center[3] < df['unique_customers'].mean() * 0.5:
            cluster_mapping[i] = 2  # Niche
        else:
            cluster_mapping[i] = 3  # Standard
    
    # Map original cluster numbers to meaningful ones
    df['cluster_type'] = df['cluster'].map(cluster_mapping)
    
    # Save results to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Clear previous clustering results
    cur.execute("DELETE FROM sanollea.PRODUCT_CLUSTERS")
    
    # Insert new clustering results
    for _, row in df.iterrows():
        cluster_type = int(row['cluster_type'])
        features_json = {
            'times_purchased': float(row['times_purchased']),
            'average_price': float(row['average_price']),
            'total_quantity_sold': float(row['total_quantity_sold']),
            'unique_customers': float(row['unique_customers'])
        }
        
        cur.execute("""
        INSERT INTO sanollea.PRODUCT_CLUSTERS (
            product_name, cluster_id, cluster_name, cluster_description, features
        )
        VALUES (%s, %s, %s, %s, %s)
        """, (
            row['product_name'],
            cluster_type,
            cluster_names[cluster_type],
            cluster_descriptions[cluster_type],
            json.dumps(features_json)
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    
    # Prepare results for API response
    clusters = []
    for i in range(4):  # 4 cluster types
        if i in df['cluster_type'].values:
            cluster_products = df[df['cluster_type'] == i]
            clusters.append({
                'id': i,
                'name': cluster_names[i],
                'description': cluster_descriptions[i],
                'count': len(cluster_products),
                'avg_price': cluster_products['average_price'].mean(),
                'avg_purchases': cluster_products['times_purchased'].mean(),
                'products': cluster_products['product_name'].tolist()
            })
    
    return clusters

def get_customer_cluster(customer_id):
    """
    Get the cluster information for a specific customer.
    
    Args:
        customer_id: ID of the customer
        
    Returns:
        Dictionary with cluster information
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
    SELECT 
        cc.cluster_id,
        cc.cluster_name,
        cc.cluster_description,
        cc.features
    FROM 
        sanollea.CUSTOMER_CLUSTERS cc
    WHERE 
        cc.customer_id = %s
    """, (customer_id,))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if result:
        return {
            'cluster_id': result['cluster_id'],
            'cluster_name': result['cluster_name'],
            'cluster_description': result['cluster_description'],
            'features': result['features']
        }
    else:
        return None

def get_product_cluster(product_name):
    """
    Get the cluster information for a specific product.
    
    Args:
        product_name: Name of the product
        
    Returns:
        Dictionary with cluster information
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
    SELECT 
        pc.cluster_id,
        pc.cluster_name,
        pc.cluster_description,
        pc.features
    FROM 
        sanollea.PRODUCT_CLUSTERS pc
    WHERE 
        pc.product_name = %s
    """, (product_name,))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if result:
        return {
            'cluster_id': result['cluster_id'],
            'cluster_name': result['cluster_name'],
            'cluster_description': result['cluster_description'],
            'features': result['features']
        }
    else:
        return None
