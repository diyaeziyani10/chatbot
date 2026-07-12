"""Vectorisation du corpus scrapé → base Chroma persistante.

Découpe les pages en fragments, calcule les embeddings avec un modèle
multilingue local (aucune donnée envoyée dans le cloud) et les stocke
dans rag_service/chroma_db.

À relancer après chaque mise à jour du corpus (rôle Administrateur,
cahier des charges section 3.2.1).

Usage : python rag_service/ingest.py
"""
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BASE_DIR / "corpus"
CHROMA_DIR = str(BASE_DIR / "chroma_db")

# Modèle d'embeddings multilingue léger (~470 Mo), exécuté en local
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_documents():
    """Charge chaque page du corpus avec son URL source en métadonnée."""
    from langchain_core.documents import Document

    docs = []
    for file in sorted(CORPUS_DIR.glob("*.txt")):
        raw = file.read_text(encoding="utf-8")
        first_line, _, body = raw.partition("\n\n")
        source = first_line.replace("SOURCE: ", "").strip()
        docs.append(Document(page_content=body, metadata={"source": source}))
    return docs


def main() -> None:
    docs = load_documents()
    if not docs:
        raise SystemExit(
            "Corpus vide — lancez d'abord : python rag_service/scraper.py"
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_documents(docs)
    print(f"{len(docs)} pages → {len(chunks)} fragments")

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    Chroma.from_documents(
        chunks, embeddings, persist_directory=CHROMA_DIR
    )
    print(f"Index vectoriel créé dans {CHROMA_DIR}")


if __name__ == "__main__":
    main()
