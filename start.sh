#!/bin/bash
# Script de démarrage pour Render : lance FastAPI en arrière-plan puis Streamlit

# Lancer le backend FastAPI sur le port 8000 (interne)
python -m uvicorn rag_service.rag_api:app --host 0.0.0.0 --port 8000 &

# Attendre que le backend soit prêt
sleep 10

# Lancer Streamlit sur le port fourni par Render ($PORT) ou 8501 par défaut
streamlit run frontend/app.py \
  --server.port=${PORT:-8501} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
