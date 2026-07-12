"""Service RAG — API HTTP locale appelée par l'action de fallback Rasa.

POST /ask  {"question": "..."}  →  {"answer": "...", "sources": [...]}

Contrainte « zéro hallucination » (cahier des charges, section 4) :
le prompt impose au LLM de répondre UNIQUEMENT à partir des extraits du
site amendis.ma retrouvés par similarité, et de dire explicitement
lorsqu'il ne sait pas.

LLM : Ollama en local par défaut (variable d'environnement OLLAMA_MODEL,
ex. "llama3.2"). Lancer d'abord :  ollama pull llama3.2

Usage : uvicorn rag_service.rag_api:app --port 8000
"""
import os
from pathlib import Path

from fastapi import FastAPI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = str(BASE_DIR / "chroma_db")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

SYSTEM_PROMPT = """Tu es l'assistant documentaire d'Amendis (distribution \
d'eau et d'électricité à Tanger et Tétouan).

RÈGLES STRICTES :
1. Réponds UNIQUEMENT à partir des extraits de documentation fournis ci-dessous.
2. Si l'information demandée n'est pas dans les extraits, réponds exactement :
   "Je n'ai pas trouvé cette information dans la documentation Amendis. \
Vous pouvez contacter le service client au 05 39 32 88 88."
3. N'invente jamais de chiffres, de tarifs, de procédures ou de coordonnées.
4. Réponds en français, de façon claire et concise (5 phrases maximum).

EXTRAITS DE LA DOCUMENTATION AMENDIS :
{context}"""

app = FastAPI(title="Service RAG Amendis")

# Chargés une seule fois au démarrage du service
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
llm = ChatOllama(model=OLLAMA_MODEL, temperature=0)
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
    return {"status": "ok", "model": OLLAMA_MODEL}
