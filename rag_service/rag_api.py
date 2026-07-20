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
import json
import os
import re
from datetime import datetime
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

# ---------------------------------------------------------------------------
# Mémoire conversationnelle persistante : un fichier JSON par utilisateur.
# Permet au bot de comprendre les questions de suivi (« et pour
# l'électricité ? ») et de se souvenir des échanges des jours précédents.
# Données personnelles : stockées uniquement en local, jamais indexées
# dans ChromaDB ; en production il faudrait consentement + durée de rétention.
# ---------------------------------------------------------------------------
MEMOIRE_DIR = BASE_DIR / "memoire"
MEMOIRE_DIR.mkdir(exist_ok=True)
MAX_ECHANGES_PROMPT = 6    # nb d'échanges passés injectés dans le prompt
MAX_ECHANGES_FICHIER = 50  # nb d'échanges conservés par utilisateur


def _fichier_memoire(user_id: str | None) -> Path | None:
    """Chemin du fichier mémoire de l'utilisateur (identifiant assaini :
    seuls lettres/chiffres/-/_ sont gardés, pour un nom de fichier sûr)."""
    slug = re.sub(r"[^a-z0-9_-]", "", (user_id or "").lower().replace(" ", "_"))[:40]
    return (MEMOIRE_DIR / f"{slug}.json") if slug else None


def charger_historique(user_id: str | None) -> list[dict]:
    f = _fichier_memoire(user_id)
    if f and f.exists():
        return json.loads(f.read_text(encoding="utf-8"))[-MAX_ECHANGES_PROMPT:]
    return []


def enregistrer_echange(user_id: str | None, question: str, reponse: str) -> None:
    f = _fichier_memoire(user_id)
    if not f:
        return  # utilisateur anonyme : pas de mémoire persistante
    hist = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    hist.append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "question": question,
        "reponse": reponse,
    })
    f.write_text(json.dumps(hist[-MAX_ECHANGES_FICHIER:], ensure_ascii=False, indent=1),
                 encoding="utf-8")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """Tu es « l'Assistant virtuel Amendis », le chatbot officiel \
d'assistance client d'Amendis — l'entreprise (groupe Veolia) chargée de la \
distribution d'eau potable et d'électricité et de l'assainissement liquide \
dans les régions de Tanger et Tétouan, au Maroc.

TON IDENTITÉ (utilise cette section quand on te pose des questions sur TOI : \
« qui es-tu ? », « que sais-tu faire ? », « comment fonctionnes-tu ? ») :
- Tu es un assistant conversationnel basé sur l'intelligence artificielle, \
disponible 24h/24 et 7j/7 pour aider les clients d'Amendis.
- Tu sais : expliquer les factures et les moyens de paiement, les abonnements, \
branchements et résiliations, la consommation d'eau et d'électricité, les \
démarches en cas de fuite ou de coupure, et orienter vers les agences ou \
l'espace client en ligne (www.amendisclient.ma).
- Tu sais aussi renseigner sur l'entreprise Amendis elle-même : carrières, \
recrutement et offres d'emploi, actualités, engagements, activités.
- Tes réponses s'appuient exclusivement sur la documentation officielle du \
site www.amendis.ma, et tu cites tes sources.
- Tu ne manipules aucune donnée personnelle : pour toute opération sur un \
contrat précis, tu orientes vers l'espace client ou le service client \
(05 39 32 88 88).

TON DOMAINE = TOUT CE QUI CONCERNE AMENDIS : ses services clients (eau, \
électricité, assainissement, factures, abonnements, agences, démarches...) \
MAIS AUSSI l'entreprise elle-même (carrières, recrutement, offres d'emploi, \
stages, actualités, engagements, activités, partenaires...). \
INTERPRÈTE L'INTENTION : avant de choisir un cas ci-dessous, demande-toi ce \
que l'utilisateur cherche réellement à obtenir, même si sa question est \
maladroite ou indirecte. EN CAS DE DOUTE, considère que la question concerne \
Amendis et cherche dans les extraits — ne refuse jamais par excès de \
prudence une question qui touche Amendis de près ou de loin.

COMMENT RÉPONDRE — choisis le cas qui correspond à la question :
1. QUESTION SUR LE DOMAINE D'AMENDIS (tel que défini ci-dessus) : réponds \
directement et avec assurance à partir des EXTRAITS fournis plus bas — sans \
préambule du type « je ne peux répondre qu'à... ». Chaque extrait commence \
par [Page Amendis : ...] qui t'indique sa page d'origine. Combine plusieurs \
extraits si nécessaire ; si l'information n'est que partielle, donne ce qui \
existe en le précisant.
2. QUESTION SUR TOI (identité, rôle, capacités, fonctionnement) : réponds \
naturellement à partir de TON IDENTITÉ ci-dessus, de façon accueillante, \
puis propose ton aide. N'utilise pas les extraits pour cela.
3. QUESTION SANS AUCUN RAPPORT AVEC AMENDIS (autre entreprise comme Maroc \
Telecom, inwi, Orange, Netflix, RADEEMA, banques... ou sujet général : météo, \
politique, mathématiques, recettes, culture générale...) : REFUSE poliment, \
SANS RÉPONDRE À LA QUESTION. Ne donne AUCUNE information sur ce sujet : ne le \
définis pas, ne l'explique pas, ne décris pas cette entreprise, ne recommande \
ni site ni service externe — même si tu connais la réponse. Dis simplement \
que tu es l'assistant d'Amendis et que ce sujet sort de ton domaine. PUIS, si \
un service Amendis analogue existe (abonnement, facture, réclamation...), \
rebondis en le proposant. Exemple : « Je suis l'assistant d'Amendis et je ne \
peux répondre qu'aux questions concernant nos services d'eau et d'électricité \
à Tanger et Tétouan. En revanche, si vous souhaitez souscrire un abonnement \
chez Amendis, je peux vous indiquer les documents nécessaires ! »
4. QUESTION DU DOMAINE D'AMENDIS mais dont la réponse n'est PAS dans les \
extraits : dis-le honnêtement : « Je n'ai pas trouvé cette information dans \
la documentation Amendis. Vous pouvez contacter le service client au \
05 39 32 88 88. »
5. QUESTION DE SUIVI ou RÉFÉRENCE À UN ÉCHANGE PRÉCÉDENT : si un historique \
de conversation est fourni, utilise-le pour comprendre les questions \
incomplètes (« et pour l'électricité ? ») et pour te souvenir de ce que \
l'utilisateur t'a déjà demandé, même un autre jour. Si l'utilisateur demande \
ce dont vous avez parlé, rappelle-le-lui précisément.
6. QUESTION AMBIGUË ou trop vague : pose UNE question de clarification au \
lieu de deviner.
7. SOIS PROACTIF : après avoir répondu à une question du domaine d'Amendis, \
termine par UNE suggestion pertinente d'action ou d'information \
complémentaire, déduite de la situation de l'utilisateur et des extraits. \
Réfléchis à ce dont il aura logiquement besoin JUSTE APRÈS : \
- il demande un abonnement d'eau → propose aussi l'abonnement d'électricité ; \
- il demande comment payer → propose l'espace client en ligne ou les autres \
moyens de paiement ; \
- il signale une fuite → propose le numéro d'urgence ou le suivi de sa \
demande ; \
- il déménage → propose la résiliation de l'ancien contrat ET le nouvel \
abonnement. \
Formule la suggestion en une phrase naturelle et engageante à la fin de ta \
réponse (ex : « Souhaitez-vous aussi... ? », « Sachez que vous pouvez \
également... »). JAMAIS de suggestion inventée : uniquement des services \
d'Amendis mentionnés dans les extraits ou dans TON IDENTITÉ. Pas de \
suggestion quand tu refuses une question hors domaine (le rebond suffit) ni \
quand tu poses une question de clarification.

RÈGLES ABSOLUES :
- N'invente JAMAIS de chiffres, tarifs, procédures, coordonnées ou liens qui \
ne figurent pas dans les extraits ou dans TON IDENTITÉ.
- Réponds en français (sauf si l'utilisateur écrit dans une autre langue), \
de façon claire, chaleureuse et concise (6 phrases maximum, listes à puces \
si utile).

EXTRAITS DE LA DOCUMENTATION AMENDIS (site www.amendis.ma) :
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
# Chaîne de secours LLM, essayée dans l'ordre à CHAQUE requête :
# 1. Groq 70b (qualité maximale) — quota gratuit : 100 000 tokens/jour
# 2. Groq 8b-instant (qualité correcte) — quota séparé, bien plus large
# 3. Ollama local (lent sur CPU, mais toujours disponible)
# → si un modèle échoue (quota épuisé, panne, pas d'internet), le suivant
#   prend le relais automatiquement : le bot ne tombe jamais en panne.
LLMS: list = []
if os.environ.get("GROQ_API_KEY"):
    from langchain_groq import ChatGroq

    LLMS.append((f"groq/{GROQ_MODEL}", ChatGroq(model=GROQ_MODEL, temperature=0)))
    LLMS.append(("groq/llama-3.1-8b-instant",
                 ChatGroq(model="llama-3.1-8b-instant", temperature=0)))
LLMS.append((f"ollama/{OLLAMA_MODEL}", ChatOllama(model=OLLAMA_MODEL, temperature=0)))

LLM_INFO = " -> ".join(nom for nom, _ in LLMS)
llm = LLMS[0][1]  # modèle principal (reformulation : voir llm_condense)
# La reformulation est une tâche simple : on la confie au modèle léger
# pour économiser le quota du 70b.
llm_condense = LLMS[1][1] if len(LLMS) > 1 else LLMS[0][1]


def generer(template, variables: dict):
    """Invoque la chaîne de secours : premier LLM qui répond gagne."""
    derniere_erreur = None
    for nom, modele in LLMS:
        try:
            return (template | modele).invoke(variables)
        except Exception as exc:  # quota épuisé, réseau, service éteint...
            derniere_erreur = exc
    raise RuntimeError(f"Aucun LLM disponible : {derniere_erreur}")
prompt = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "{history}QUESTION DE L'UTILISATEUR : {question}")]
)

# ---------------------------------------------------------------------------
# Reformulation : une réponse courte (« oui », « et pour l'électricité ? »)
# ne trouve rien par similarité vectorielle. Quand un historique existe, on
# demande d'abord au LLM de reformuler la question en QUESTION AUTONOME, et
# c'est elle qui interroge ChromaDB. La question originale + l'historique
# restent utilisés pour la rédaction de la réponse finale.
# ---------------------------------------------------------------------------
CONDENSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "À partir de l'historique de conversation, reformule le "
               "dernier message de l'utilisateur en UNE question autonome et "
               "complète sur les services d'Amendis (eau/électricité). "
               "Si le message fait référence à une suggestion du bot "
               "(« oui », « les deux », « d'accord »...), la question "
               "autonome reprend le contenu de cette suggestion. Si le "
               "message est déjà autonome, renvoie-le tel quel. Réponds "
               "UNIQUEMENT par la question reformulée, sans commentaire."),
    ("human", "{history}Dernier message de l'utilisateur : {question}\n\n"
              "Question autonome :"),
])


def question_autonome(question: str, history: str) -> str:
    """Reformule une question contextuelle en question autonome (pour la
    recherche vectorielle). Sans historique ou en cas d'erreur : inchangée."""
    if not history:
        return question
    try:
        r = (CONDENSE_PROMPT | llm_condense).invoke(
            {"history": history, "question": question}
        )
        reformulee = r.content.strip().strip('"')
        return reformulee or question
    except Exception:
        return question


class Question(BaseModel):
    question: str
    user_id: str | None = None  # identifiant fourni par le front (mémoire)


@app.post("/ask")
def ask(q: Question) -> dict:
    # 1. Historique de CET utilisateur (sessions précédentes incluses)
    hist = charger_historique(q.user_id)
    if hist:
        lignes = [
            f"[{h['date']}] Utilisateur : {h['question']}\n"
            f"[{h['date']}] Toi : {h['reponse'][:300]}"
            for h in hist
        ]
        history = ("HISTORIQUE DES ÉCHANGES AVEC CET UTILISATEUR "
                   "(du plus ancien au plus récent) :\n"
                   + "\n".join(lignes) + "\n\n")
    else:
        history = ""

    # 2. Recherche : avec la question AUTONOME (reformulée si contextuelle)
    q_recherche = question_autonome(q.question, history)
    docs = retriever.invoke(q_recherche)
    context = "\n\n---\n\n".join(d.page_content for d in docs)
    sources = sorted({d.metadata.get("source", "") for d in docs})

    # 3. Rédaction : avec la question ORIGINALE + l'historique
    #    (generer() essaie 70b → 8b → Ollama jusqu'à obtenir une réponse)
    result = generer(
        prompt, {"context": context, "history": history, "question": q.question}
    )

    enregistrer_echange(q.user_id, q.question, result.content)
    return {"answer": result.content, "sources": sources,
            "question_recherche": q_recherche}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": LLM_INFO}
