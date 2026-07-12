"""Scraping du site public www.amendis.ma pour constituer le corpus RAG.

Petit crawler poli : il part de pages « graines » (FAQ, services...),
suit uniquement les liens internes du domaine, et sauvegarde le texte
nettoyé de chaque page dans rag_service/corpus/*.txt (une page = un fichier,
avec l'URL source en première ligne pour la traçabilité des réponses).

Usage : python rag_service/scraper.py
"""
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.amendis.ma"
SEED_URLS = [
    f"{BASE}/fr",
    f"{BASE}/fr/faq",
]
MAX_PAGES = 60          # garde-fou : taille max du crawl
DELAY_SECONDS = 1.0     # politesse : 1 requête/seconde
CORPUS_DIR = Path(__file__).resolve().parent / "corpus"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (PoC chatbot stage - usage academique)"
}

# Balises non informatives à supprimer avant extraction du texte
NOISE_TAGS = ["script", "style", "nav", "header", "footer", "form", "noscript"]


def is_internal(url: str) -> bool:
    """Ne suivre que les pages françaises du site public."""
    parsed = urlparse(url)
    return (
        parsed.netloc in ("", "www.amendis.ma")
        and parsed.path.startswith("/fr")
        and not any(parsed.path.endswith(ext) for ext in (".pdf", ".jpg", ".png", ".zip"))
    )


def clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n")
    # Compacter les lignes vides et espaces multiples
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    return "\n".join(l for l in lines if len(l) > 2)


def slugify(url: str) -> str:
    path = urlparse(url).path.strip("/").replace("/", "_") or "accueil"
    return re.sub(r"[^a-zA-Z0-9_-]", "", path)[:80] + ".txt"


def crawl() -> None:
    CORPUS_DIR.mkdir(exist_ok=True)
    to_visit = list(SEED_URLS)
    seen = set(to_visit)
    saved = 0

    while to_visit and saved < MAX_PAGES:
        url = to_visit.pop(0)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  ! échec {url} : {exc}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # Découverte de nouveaux liens internes
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"]).split("#")[0].split("?")[0]
            if is_internal(link) and link not in seen:
                seen.add(link)
                to_visit.append(link)

        text = clean_text(soup)
        if len(text) > 200:  # ignorer les pages quasi vides
            out = CORPUS_DIR / slugify(url)
            out.write_text(f"SOURCE: {url}\n\n{text}", encoding="utf-8")
            saved += 1
            print(f"  [{saved:02d}] {url}")

        time.sleep(DELAY_SECONDS)

    print(f"\nTerminé : {saved} pages sauvegardées dans {CORPUS_DIR}")


if __name__ == "__main__":
    crawl()
