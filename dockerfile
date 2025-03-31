# Étape 1 : Utiliser une image Python officielle
FROM python:3.12-slim

# Étape 2 : Installer Tesseract OCR et ses dépendances système
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-fra \
    imagemagick \
    zbar-tools \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libpq-dev \
    gcc \
    wget \
    curl \
    tk-dev \
    python3-tk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Étape 3 : Transformer les arguments en variables d'environnement
ENV DB_HOST="projetocr-psqlflexibleserver.postgres.database.azure.com"
ENV DB_PORT="5432"
ENV DB_NAME="postgres"
ENV DB_USER="psqladmin"
ENV DB_PASSWORD="GRETAP4!2025***"

ENV VISION_ENDPOINT="https://francecentral.api.cognitive.microsoft.com/"
ENV VISION_KEY="5b3903aa12104b8c9e036e01c9ef6f80"

# Étape 3 : Mettre à jour pip
RUN pip install --upgrade pip

# Étape 4 : Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Étape 5 : Copier d'abord les requirements pour profiter du cache Docker
COPY requirements.txt .

# Étape 6 : Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Étape 7 : Copier le reste des fichiers nécessaires dans le conteneur
COPY . .

# Étape 8 : Créer les répertoires nécessaires et s'assurer qu'ils ont les bonnes permissions
RUN mkdir -p data uploads && chmod -R 777 data uploads

# Étape 9 : Exposer le port utilisé par FastAPI
EXPOSE 8000

# Étape 11 : Commande pour exécuter l'application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]