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

# Lignes de navigation du site (fil d'Ariane, tri, pagination) : du bruit qui
# pollue les fragments et fausse la recherche par similarité → on les retire.
NOISE_LINES = {
    "Home", "Haut", "Précédent", "Suivant", "Read more", "Sort by:",
    "Reverse", "Chronological", "Médias", "News", "Nos activités",
    "La relation client", "Client particulier",
}


def page_title(source_url: str) -> str:
    """Titre lisible dérivé de l'URL (ex : .../qui-sommes-nous/bref
    → « qui sommes nous bref ») ; sert à contextualiser les fragments."""
    path = source_url.rstrip("/").split("/fr", 1)[-1]
    return path.replace("/", " ").replace("-", " ").replace("_", " ").strip() or "accueil"


def load_documents():
    """Charge chaque page du corpus (URL source en métadonnée, bruit filtré)."""
    from langchain_core.documents import Document

    docs = []
    for file in sorted(CORPUS_DIR.glob("*.txt")):
        raw = file.read_text(encoding="utf-8")
        first_line, _, body = raw.partition("\n\n")
        source = first_line.replace("SOURCE: ", "").strip()
        body = "\n".join(
            l for l in body.splitlines() if l.strip() not in NOISE_LINES
        )
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

    # Contextualisation : chaque fragment commence par le titre de sa page,
    # pour que la recherche par similarité sache d'où il vient (sinon un
    # fragment du milieu d'une page ne contient aucun indice sur son sujet).
    for c in chunks:
        titre = page_title(c.metadata.get("source", ""))
        c.page_content = f"[Page Amendis : {titre}]\n{c.page_content}"

    print(f"{len(docs)} pages → {len(chunks)} fragments")

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    Chroma.from_documents(
        chunks, embeddings, persist_directory=CHROMA_DIR
    )
    print(f"Index vectoriel créé dans {CHROMA_DIR}")


if __name__ == "__main__":
    main()
