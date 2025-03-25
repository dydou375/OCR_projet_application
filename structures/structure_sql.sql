-- Création du schéma dylan (visible dans votre diagramme)
CREATE SCHEMA IF NOT EXISTS dylan;

-- Table client
CREATE TABLE dylan.utilisateur (
    email_personne VARCHAR(500) PRIMARY KEY,
    nom_personne VARCHAR(500),
    genre VARCHAR(50),
    adresse VARCHAR(500),
    date_anniversaire DATE
    );

-- Table Facture
CREATE TABLE dylan.facture (
    nom_facture VARCHAR(500) PRIMARY KEY,
    date_facture DATE,
    total_facture FLOAT,
    email_personne VARCHAR(500),
    FOREIGN KEY (email_personne) REFERENCES dylan.utilisateur(email_personne)
);

    -- Table Article
CREATE TABLE dylan.article (
    nom_facture VARCHAR(500),
    nom_article VARCHAR(500),
    quantite INTEGER,
    prix FLOAT,
    PRIMARY KEY (nom_facture, nom_article),
    FOREIGN KEY (nom_facture) REFERENCES dylan.facture(nom_facture)
    );

    -- Table log
CREATE TABLE dylan.log (
    id SERIAL PRIMARY KEY,
    time TIMESTAMP,
    fichier VARCHAR(500),
    erreur TEXT
);

-- Modification de la table utilisateur
ALTER TABLE dylan.utilisateur 
    ALTER COLUMN email_personne TYPE VARCHAR(500),
    ALTER COLUMN nom_personne TYPE VARCHAR(500),
    ALTER COLUMN adresse TYPE VARCHAR(500);

-- Modification de la table facture
ALTER TABLE dylan.facture 
    ALTER COLUMN nom_facture TYPE VARCHAR(500),
    ALTER COLUMN email_personne TYPE VARCHAR(500);

-- Modification de la table article
ALTER TABLE dylan.article 
    ALTER COLUMN nom_facture TYPE VARCHAR(500),
    ALTER COLUMN nom_article TYPE VARCHAR(500);

-- Modification de la table log
ALTER TABLE dylan.log 
    ALTER COLUMN fichier TYPE VARCHAR(500);