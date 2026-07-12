# Chatbot Amendis — PoC (Stage d'observation)

Agent conversationnel pour l'assistance client Amendis (eau / électricité).

## Architecture

```
                        ┌─────────────────────┐
  Utilisateur ──────────►  Front-end Streamlit │
                        │     (frontend/)      │
                        └─────────┬───────────┘
                                  │ API REST (port 5005)
                        ┌─────────▼───────────┐
                        │    Rasa (NLU +       │   scénarios stricts
                        │    dialogue)         │──► actions/actions.py
                        │    (rasa_bot/)       │        │
                        └─────────┬───────────┘        ▼
                                  │ fallback      SQLite locale
                                  │ (question     (database/amendis.db)
                                  │  hors scénario)
                        ┌─────────▼───────────┐
                        │   Service RAG        │   corpus scrapé depuis
                        │   LangChain + LLM    │◄── www.amendis.ma
                        │   (rag_service/,     │
                        │    port 8000)        │
                        └─────────────────────┘
```

Principes de sécurité (cahier des charges) :
- Les données clients (contrats, factures) sont traitées **uniquement** par les
  Custom Actions Rasa + SQLite. Elles ne transitent jamais par le LLM.
- Le RAG répond **exclusivement** à partir du corpus scrapé sur www.amendis.ma
  (zéro hallucination : si l'info n'est pas dans le corpus, le bot le dit).
- www.amendisclient.ma (espace client) est le SI que la base SQLite simule ;
  le bot y redirige l'utilisateur pour les actions réelles (paiement).

## Deux environnements virtuels (obligatoire)

Rasa 3.6 requiert `pydantic` v1, LangChain requiert `pydantic` v2 : ils sont
incompatibles dans un même environnement. D'où deux venvs (Python 3.10) :

| venv         | Contenu                          | Fichier de dépendances          |
|--------------|----------------------------------|---------------------------------|
| `venv_rasa`  | Rasa + SDK actions               | `requirements-rasa.txt`         |
| `venv_rag`   | LangChain, scraper, Streamlit    | `rag_service/requirements.txt`  |

## Installation

```powershell
# 1. venv Rasa
python -m venv venv_rasa
venv_rasa\Scripts\pip install -r requirements-rasa.txt

# 2. venv RAG / front
python -m venv venv_rag
venv_rag\Scripts\pip install -r rag_service\requirements.txt

# 3. Base de données de simulation
venv_rag\Scripts\python database\init_db.py

# 4. Corpus RAG (scraping amendis.ma puis vectorisation)
venv_rag\Scripts\python rag_service\scraper.py
venv_rag\Scripts\python rag_service\ingest.py

# 5. Entraîner le modèle Rasa
cd rasa_bot
..\venv_rasa\Scripts\rasa train
```

## Lancement (4 terminaux)

```powershell
# T1 — serveur d'actions Rasa
cd rasa_bot ; ..\venv_rasa\Scripts\rasa run actions

# T2 — service RAG
venv_rag\Scripts\uvicorn rag_service.rag_api:app --port 8000

# T3 — serveur Rasa (API REST)
cd rasa_bot ; ..\venv_rasa\Scripts\rasa run --enable-api --cors "*"

# T4 — front-end Streamlit
venv_rag\Scripts\streamlit run frontend\app.py
```

Pour tester sans front-end : `rasa shell` (T3 remplacé).
