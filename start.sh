#!/bin/bash
# Script de démarrage pour Render : lance FastAPI en arrière-plan puis Streamlit

# Démarrer FastAPI en arrière-plan (sur le port 8000)
echo "Démarrage de l'API FastAPI..."
uvicorn rag_service.rag_api:app --host 0.0.0.0 --port 8000 &

# Attendre un peu que l'API soit prête
sleep 3

# Démarrer Streamlit au premier plan (sur le port 7860 pour Hugging Face Spaces)
echo "Démarrage de l'interface Streamlit..."
streamlit run frontend/app.py --server.port 7860 --server.address 0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
