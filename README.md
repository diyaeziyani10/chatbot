# Chatbot Amendis — PoC (Stage d'observation)

Agent conversationnel d'assistance client Amendis (eau / électricité),
basé sur un système **RAG** (Retrieval-Augmented Generation) qui répond
exclusivement à partir du contenu du site officiel www.amendis.ma.

## Architecture

```
              ┌─────────────────────┐
Utilisateur ──►  Front-end Streamlit │  (frontend/app.py, port 8501)
              └─────────┬───────────┘
                        │ HTTP  POST /chat  {question, user_id}
              ┌─────────▼────────────────────────────────┐
              │        Service RAG (FastAPI, port 8000)   │
              │  rag_service/rag_api.py                   │
              │                                           │
              │  1. Politesses (bonjour/merci…) ─► réponse│
              │     fixe instantanée, sans LLM            │
              │  2. Sinon :                               │
              │     • mémoire par utilisateur (memoire/)  │
              │     • reformulation « condense question » │
              │     • recherche vectorielle (ChromaDB)    │
              │     • génération (prompt + extraits)      │
              └─────────┬─────────────────────┬───────────┘
                        │ embeddings          │ génération
                 ChromaDB (chroma_db/)   Groq → Ollama (secours)
                 corpus www.amendis.ma
```

**Historique** : le projet utilisait initialement **Rasa** (NLU + dialogue)
et une base **SQLite**. Les deux ont été retirés au fil des itérations :
le RAG assure désormais seul la compréhension, le routage et les réponses
(les fichiers `rasa_bot/` et `database/` sont conservés pour le rapport).

## Principes (cahier des charges)

- **Zéro hallucination** : le bot répond uniquement à partir du corpus scrapé
  sur www.amendis.ma. Si l'info n'y est pas, il le dit. Les données factuelles
  (adresses, numéros) sont recopiées à l'identique, jamais inventées.
- **Aucune donnée client** dans le système : pour une opération sur un contrat,
  le bot redirige vers l'espace client (www.amendisclient.ma) ou le 05 39 32 88 88.
- **Confidentialité** : seuls la question et des extraits du site *public*
  partent vers le LLM. La mémoire conversationnelle reste locale (`memoire/`).

## Installation

Prérequis : **Python 3.10**, **Ollama** (secours LLM local, https://ollama.com),
~10 Go d'espace disque.

```powershell
# 1. Environnement Python (un seul suffit pour faire tourner le bot)
python -m venv venv_rag
venv_rag\Scripts\pip install -r rag_service\requirements.txt

# 2. Clé API Groq (LLM cloud) : créer le fichier rag_service\.env
#    avec la ligne :  GROQ_API_KEY=gsk_votre_cle
#    (compte gratuit sur https://console.groq.com)

# 3. Corpus : scraping d'amendis.ma puis vectorisation
venv_rag\Scripts\python rag_service\scraper.py
venv_rag\Scripts\python rag_service\ingest.py
#    NB : le fichier corpus/fr_nos-agences.txt (agences, donnée manuelle) est
#    versionné ; il est réindexé automatiquement par ingest.py.

# 4. Modèle LLM de secours local
ollama pull llama3.2
```

## Lancement (2 terminaux)

```powershell
# T1 — service RAG (attendre "Uvicorn running", ~30 s de chargement)
venv_rag\Scripts\uvicorn rag_service.rag_api:app --port 8000

# T2 — front-end Streamlit (ouvre http://localhost:8501)
venv_rag\Scripts\streamlit run frontend\app.py
```

Vérifier le LLM actif : http://localhost:8000/health
(`groq/...` = cloud rapide ; `ollama/...` = secours local).

## Structure

```
frontend/app.py            Interface de chat (appelle le RAG /chat)
rag_service/
  scraper.py               Crawler www.amendis.ma → corpus/*.txt
  ingest.py                corpus → fragments → embeddings → ChromaDB
  rag_api.py               Service RAG : /chat (politesses + RAG + mémoire)
  corpus/                  Pages scrapées + fr_nos-agences.txt (manuel)
  .env                     GROQ_API_KEY (NON versionné)
  memoire/                 Mémoire par utilisateur (NON versionné)
docs/                      Documentation et plan de test (TESTS.md)
rasa_bot/, database/       Conservés pour l'historique (plus utilisés)
```
