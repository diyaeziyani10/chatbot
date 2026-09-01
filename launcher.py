import os
import sys
import threading
import uvicorn
from streamlit.web import cli as stcli

def start_api():
    # Lancement de l'API FastAPI
    # Attention: dans pyinstaller, il vaut mieux importer l'app directement 
    # plutôt que par string "rag_service.rag_api:app"
    from rag_service.rag_api import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

def main():
    # Démarre l'API dans un thread séparé
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # Prépare l'environnement pour Streamlit
    if getattr(sys, 'frozen', False):
        frontend_path = os.path.join(sys._MEIPASS, 'frontend', 'app.py')
    else:
        frontend_path = os.path.join(os.path.dirname(__file__), 'frontend', 'app.py')

    # Lance Streamlit dans le thread principal
    sys.argv = ["streamlit", "run", frontend_path, "--server.headless=true", "--browser.serverAddress=localhost", "--server.port=8501"]
    
    # Empêche streamlit de quitter immédiatement
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
