import os
import psycopg2
from dotenv import load_dotenv
import time
from back_end.classe.validate_date import validate_date


load_dotenv()

def create_tables():
    # Connexion à la base de données
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()

    # Script SQL pour créer les tables dans un schéma spécifique
    create_table_query = """
    CREATE SCHEMA IF NOT EXISTS dylan;

    -- Table utilisateur
    CREATE TABLE IF NOT EXISTS dylan.utilisateur (
        email_personne VARCHAR(255) PRIMARY KEY,
        nom_personne VARCHAR(255),
        genre VARCHAR(50),
        adresse VARCHAR(500),
        date_anniversaire DATE
        );

    -- Table Facture
    CREATE TABLE IF NOT EXISTS dylan.facture (
        nom_facture VARCHAR(255) PRIMARY KEY,
        date_facture DATE,
        total_facture float,
        email_personne VARCHAR(255),
        FOREIGN KEY (email_personne) REFERENCES dylan.utilisateur(email_personne)
    );

    -- Table Article
    CREATE TABLE IF NOT EXISTS dylan.article (
        nom_facture VARCHAR(255),
        nom_article VARCHAR(255),
        quantite float,
        prix float,
        PRIMARY KEY (nom_facture, nom_article),
        FOREIGN KEY (nom_facture) REFERENCES dylan.facture(nom_facture)
        );

    -- Table log
    CREATE TABLE IF NOT EXISTS dylan.log (
        id SERIAL PRIMARY KEY,
        time TIMESTAMP,
        fichier VARCHAR(255),
        erreur TEXT
    );"""
    
    # Exécution du script SQL
    cur.execute(create_table_query)
    conn.commit()

    # Fermeture de la connexion
    cur.close()
    conn.close()
    
def save_invoice_data_to_db_improved(invoice_data):
    """Enregistre les données de la facture dans la base de données."""
    # Connexion à la base de données
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()

    try:
        # Validation de la date avant insertion
        valid_date = validate_date(invoice_data.get("issue_date"))
        if not valid_date:
            print(f"⚠️ Date invalide détectée: {invoice_data.get('issue_date')}. Utilisation de la date du jour.")
            valid_date = time.strftime("%Y-%m-%d")
            
        # Vérification et insertion/mise à jour des données du client
        customer_id = None
        
        # Vérifier si l'email existe avant de faire la requête
        if invoice_data.get("email"):
            cur.execute("""
                SELECT email_personne FROM dylan.utilisateur WHERE email_personne = %s
            """, (invoice_data["email"],))
            customer = cur.fetchone()
            
            if customer:
                customer_id = customer[0]
                print(f"Client existant trouvé avec l'ID: {customer_id}")
                # Mise à jour des informations du client existant
                cur.execute("""
                    UPDATE dylan.utilisateur 
                    SET nom_personne = %s, adresse = %s 
                    WHERE email_personne = %s
                """, (invoice_data["client"], invoice_data["address"], customer_id))
                print("Informations du client mises à jour")
        
        # Si le client n'existe pas ou si l'email n'est pas disponible
        if not customer_id:
            print("Création d'un nouveau client...")
            
            client_name = invoice_data.get("client", "Client inconnu")
            client_email = invoice_data.get("email", f"inconnu_{int(time.time())}@placeholder.com")
            client_address = invoice_data.get("address", "Adresse inconnue")
            
            try:
                cur.execute("""
                    INSERT INTO dylan.utilisateur (nom_personne, email_personne, adresse)
                    VALUES (%s, %s, %s)
                    RETURNING email_personne
                """, (client_name, client_email, client_address))
                customer_id = cur.fetchone()[0]
                print(f"Nouveau client créé avec l'ID: {customer_id}")
            except psycopg2.Error as e:
                # Gérer les erreurs potentielles lors de l'insertion
                print(f"Erreur lors de la création du client: {e}")
                # Créer une entrée de journal pour l'erreur
                cur.execute("""
                    INSERT INTO dylan.log (time, fichier, erreur)
                    VALUES (NOW(), 'save_invoice_data_to_db', %s)
                """, (f"Erreur création client: {e}",))
                conn.commit()
                # Créer un client générique pour pouvoir continuer
                cur.execute("""
                    INSERT INTO dylan.utilisateur (nom_personne, email_personne, adresse)
                    VALUES ('Client temporaire', 'temp_client@placeholder.com', 'À compléter')
                    RETURNING email_personne
                """)
                customer_id = cur.fetchone()[0]
                print(f"Client temporaire créé avec l'ID: {customer_id}")
        
        # Vérification et insertion/mise à jour des données de la facture
        cur.execute("""
            SELECT nom_facture FROM dylan.facture WHERE nom_facture = %s
        """, (invoice_data["invoice_number"],))
        invoice = cur.fetchone()
        
        if invoice:
            invoice_id = invoice[0]
            cur.execute("""
                UPDATE dylan.facture 
                SET date_facture = %s, total_facture = %s, email_personne = %s 
                WHERE nom_facture = %s
            """, (valid_date, invoice_data["total"], customer_id, invoice_id))
        else:
            cur.execute("""
                INSERT INTO dylan.facture (nom_facture, date_facture, total_facture, email_personne)
                VALUES (%s, %s, %s, %s)
                RETURNING nom_facture
            """, (invoice_data["invoice_number"], valid_date, invoice_data["total"], customer_id))
            invoice_id = cur.fetchone()[0]

        # Insertion des articles
        for item in invoice_data["items"]:
            cur.execute("""
                INSERT INTO dylan.article (nom_facture, nom_article, quantite, prix)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (nom_facture, nom_article) DO UPDATE 
                SET quantite = %s, prix = %s
            """, (
                invoice_data["invoice_number"], 
                item["name"], 
                item["quantity"], 
                item["unit_price"],
                item["quantity"],
                item["unit_price"]
            ))

        # Validation des transactions
        conn.commit()
        print("Données de la facture enregistrées dans la base de données.")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de l'enregistrement de la facture {invoice_data.get('invoice_number')}: {e}")
        # Journalisation de l'erreur
        try:
            cur.execute("""
                INSERT INTO dylan.log (time, fichier, erreur)
                VALUES (NOW(), 'save_invoice_data_to_db', %s)
            """, (f"Erreur facture {invoice_data.get('invoice_number')}: {e}",))
            conn.commit()
        except:
            pass
    finally:
        # Fermeture de la connexion
        cur.close()
        conn.close()
        
def update_customer_from_qr(qr_data):
    """Met à jour les informations client à partir des données du QR code."""
    # Connexion à la base de données
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()
    
    try:
        # Rechercher la facture par son numéro
        cur.execute("""
            SELECT nom_facture, email_personne FROM dylan.facture 
            WHERE nom_facture = %s
        """, (qr_data["invoice_number"],))
        
        invoice = cur.fetchone()
        
        if invoice:
            nom_facture, email_personne = invoice
            print(f"Facture trouvée avec ID: {nom_facture}, Client ID: {email_personne}")
            
            # Mise à jour des informations client
            cur.execute("""
                UPDATE dylan.utilisateur 
                SET genre = %s, date_anniversaire = %s
                WHERE email_personne = %s
            """, (qr_data.get("genre"), qr_data.get("birthdate"), email_personne))
            
            conn.commit()
            print(f"✅ Informations client mises à jour: Genre={qr_data.get('genre')}, Naissance={qr_data.get('birthdate')}")
        else:
            print(f"❌ Aucune facture trouvée avec le numéro: {qr_data['invoice_number']}")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de la mise à jour: {e}")
        cur.execute("""
            INSERT INTO dylan.log (time, fichier, erreur)
            VALUES (NOW(), 'update_customer_from_qr', %s)
        """, (str(e),))
        conn.commit()
    
    finally:
        cur.close()
        conn.close()