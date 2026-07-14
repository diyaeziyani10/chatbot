"""Service RAG — API HTTP locale appelée par l'action de fallback Rasa.

POST /ask  {"question": "..."}  →  {"answer": "...", "sources": [...]}

Contrainte « zéro hallucination » (cahier des charges, section 4) :
le prompt impose au LLM de répondre UNIQUEMENT à partir des extraits du
site amendis.ma retrouvés par similarité, et de dire explicitement
lorsqu'il ne sait pas.

LLM : Groq (API cloud, rapide) si une clé GROQ_API_KEY est présente dans
rag_service/.env ; sinon repli automatique sur Ollama en local (llama3.2).
Le cahier des charges (section 5.2) autorise les deux : « API cloud ou
modèle local léger via Ollama ». Seuls la question et des extraits du site
PUBLIC amendis.ma partent vers le cloud — jamais de donnée client.

Usage : uvicorn rag_service.rag_api:app --port 8000
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # charge GROQ_API_KEY si le fichier existe

CHROMA_DIR = str(BASE_DIR / "chroma_db")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """Tu es l'assistant documentaire d'Amendis (distribution \
d'eau et d'électricité à Tanger et Tétouan).

TA MISSION : aider l'utilisateur en répondant à sa question à partir des \
extraits du site officiel amendis.ma fournis ci-dessous. Examine attentivement \
CHAQUE extrait avant de répondre : la réponse s'y trouve souvent, même \
formulée différemment de la question.

COMMENT UTILISER LES EXTRAITS :
1. Chaque extrait commence par [Page Amendis : ...] — ce titre t'indique de \
quelle page du site il provient et donc de quel sujet il parle.
2. Si les extraits ne couvrent qu'une partie de la question, réponds avec ce \
qu'ils contiennent et précise que l'information est partielle (par exemple : \
"voici ce que mentionne le site, la liste n'est peut-être pas complète").
3. Combine plusieurs extraits si nécessaire pour construire ta réponse.

LIMITES À RESPECTER :
4. Ne réponds qu'à partir des extraits : n'invente jamais de chiffres, de \
tarifs, de procédures ou de coordonnées qui n'y figurent pas.
5. En DERNIER RECOURS seulement, si après examen aucun extrait ne contient \
d'élément de réponse, réponds : "Je n'ai pas trouvé cette information dans \
la documentation Amendis. Vous pouvez contacter le service client au \
05 39 32 88 88."
6. Réponds en français, de façon claire et concise (5 phrases maximum).

EXTRAITS DE LA DOCUMENTATION AMENDIS :
{context}"""

app = FastAPI(title="Service RAG Amendis")

# Chargés une seule fois au démarrage du service
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
# MMR : privilégie des fragments PERTINENTS mais VARIÉS (évite 4 fragments
# de la même page) ; fetch_k=20 candidats, 6 retenus.
retriever = vectorstore.as_retriever(
    search_type="mmr", search_kwargs={"k": 6, "fetch_k": 20}
)
# Groq (cloud, ~2-4 s) en priorité ; Ollama (local, lent sur CPU) en secours.
if os.environ.get("GROQ_API_KEY"):
    from langchain_groq import ChatGroq

    llm = ChatGroq(model=GROQ_MODEL, temperature=0)
    LLM_INFO = f"groq/{GROQ_MODEL}"
else:
    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0)
    LLM_INFO = f"ollama/{OLLAMA_MODEL}"
prompt = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "{question}")]
)


class Question(BaseModel):
    question: str


@app.post("/ask")
def ask(q: Question) -> dict:
    docs = retriever.invoke(q.question)
    context = "\n\n---\n\n".join(d.page_content for d in docs)
    sources = sorted({d.metadata.get("source", "") for d in docs})

    chain = prompt | llm
    result = chain.invoke({"context": context, "question": q.question})

    return {"answer": result.content, "sources": sources}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": LLM_INFO}
