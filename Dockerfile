# Utiliser une image Python officielle
FROM python:3.10-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier le fichier des dépendances
COPY requirements.txt .

# Installer les dépendances
# Note: On utilise --no-cache-dir pour garder l'image légère
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste des fichiers du projet
COPY . .

# Rendre le script de démarrage exécutable
RUN chmod +x start.sh

# Exposer les ports nécessaires
# 7860 est le port par défaut pour Streamlit sur Hugging Face Spaces
# 8000 est pour l'API FastAPI
EXPOSE 7860
EXPOSE 8000

# Démarrer le script principal qui lance FastAPI et Streamlit
CMD ["bash", "start.sh"]
