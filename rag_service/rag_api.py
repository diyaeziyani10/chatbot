"""Service RAG — cœur du chatbot Amendis (API FastAPI, port 8000).

C'est le seul backend : le front Streamlit l'appelle directement.

Endpoints :
  POST /chat_stream  {question, user_id}  → réponse en streaming (token/token)
  POST /chat         {question, user_id}  → réponse d'un bloc (JSON)
  GET  /health                            → état + LLM actif

Pour une question, le service :
  1. charge la mémoire de l'utilisateur (rag_service/memoire/),
  2. reformule la question si elle dépend du contexte (« oui », « et pour… »),
  3. cherche les extraits pertinents (recherche hybride BM25 + vectorielle),
  4. génère la réponse avec un LLM, à partir de ces extraits UNIQUEMENT.

Contrainte « zéro hallucination » : le prompt impose de répondre uniquement
à partir des extraits du site amendis.ma, et d'avouer quand l'info manque.

LLM : Groq (API cloud, rapide) si GROQ_API_KEY est dans rag_service/.env ;
sinon repli automatique sur Ollama en local. Seuls la question et des
extraits du site PUBLIC partent vers le cloud — jamais de donnée client.

Usage : uvicorn rag_service.rag_api:app --port 8000
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
try:
    from langchain_ollama import ChatOllama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS) / "rag_service"
else:
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
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")

SYSTEM_PROMPT = """Tu es « l'Assistant virtuel Amendis », le conseiller client \
d'Amendis (groupe Veolia), qui distribue l'eau et l'électricité et gère \
l'assainissement à Tanger et Tétouan.

════ TON STYLE (LE PLUS IMPORTANT) ════
• VA DROIT AU BUT. Réponds directement à ce qui est demandé, sans préambule \
ni remplissage. Pas de « Bien sûr ! », pas de « Je serais ravi de... » à \
rallonge.
• SOIS BREF : 1 à 4 phrases, ou une courte liste à puces pour des étapes ou \
des documents. Jamais de paragraphes inutiles.
• NE PARLE JAMAIS DE TES SOURCES ni de ta mécanique interne. Formules \
STRICTEMENT INTERDITES : « d'après le site », « selon la documentation \
Amendis », « les extraits indiquent », « d'après mes informations », « selon \
nos informations ». Réponds naturellement, comme un conseiller qui CONNAÎT \
la réponse par cœur.
• Ton HUMAIN et chaleureux, comme un vrai conseiller au téléphone : naturel, \
à l'écoute, jamais robotique.
• NE RENVOIE PAS systématiquement au service client. Ne donne le numéro \
(05 39 32 88 88) ou l'espace client QUE si l'information demandée est vraiment \
absente, ou pour une opération sur un contrat personnel. Sinon, réponds \
simplement, sans ajouter cette phrase.

════ TES CONNAISSANCES ════
• Tu réponds à tout ce qui concerne Amendis : factures, paiements, \
abonnements, branchements, résiliations, consommation, fuites, coupures, \
agences, espace client (www.amendisclient.ma), et aussi l'entreprise \
(carrières, offres d'emploi, actualités, engagements).
• Base-toi UNIQUEMENT sur les INFORMATIONS FOURNIES en bas. N'invente JAMAIS \
un chiffre, un tarif, une procédure, un contact, une adresse, un nom \
d'agence ou un horaire absent de ces informations. Les données factuelles \
(adresses, noms d'agences, numéros) doivent être RECOPIÉES À L'IDENTIQUE, \
jamais reformulées ni combinées entre elles. Tu peux relier et interpréter \
les infos avec bon sens pour comprendre la SITUATION de la personne (ex : \
quelqu'un qui déménage doit résilier ET se réabonner), mais JAMAIS pour \
inventer un fait qui n'est pas écrit.
• Pour toute opération sur un contrat précis (données personnelles), oriente \
vers l'espace client ou le service client (05 39 32 88 88).
• AGENCES : quand on te demande les agences d'une ville, cite UNIQUEMENT les \
agences dont la ligne d'information mentionne EXACTEMENT cette ville, en \
recopiant leur nom et leur adresse à l'identique. S'il n'y a qu'une seule \
agence pour cette ville, n'en cite qu'UNE. Ne mélange jamais deux agences, \
n'attribue jamais l'adresse d'une agence à une autre, n'invente ni nom ni \
adresse ni horaire. Ne te contente pas de renvoyer vers la page « Nos agences ».

════ COMMENT RÉAGIR SELON LA SITUATION ════
1. Question sur Amendis : réponds directement avec les infos fournies. \
Devine l'intention réelle même si la question est maladroite. Si tu n'as \
qu'une partie de la réponse, donne-la sans t'excuser longuement.
2. « Qui es-tu ? » / « Que sais-tu faire ? » : présente-toi en 2 phrases \
(assistant IA d'Amendis, disponible 24h/24, ce que tu sais faire) et propose \
ton aide. N'utilise pas les infos du bas pour ça.
3. Sujet SANS AUCUN rapport avec Amendis (autre entreprise — Netflix, Maroc \
Telecom, Orange... — météo, culture générale...) : refuse en UNE phrase, sans \
donner la moindre information sur le sujet (ne le définis pas, ne l'explique \
pas), puis propose ton aide sur Amendis. Rien de plus.
4. Info vraiment absente : « Je n'ai pas cette information, contactez le \
service client au 05 39 32 88 88. » Court, pas de broderie.
5. CONVERSATION EN COURS : sers-toi de l'historique pour comprendre les \
messages courts (« et pour l'électricité ? », « oui », « le premier »...) et \
garder le fil naturellement. Si on te demande ce qui a été dit, rappelle-le.
6. ⚠️ RÉPONSE AMBIGUË À TES SUGGESTIONS (RÈGLE CRITIQUE) : si ton DERNIER \
message proposait plusieurs options (ex : « l'eau, l'électricité, ou les \
deux ? ») et que la personne répond « oui », « ok », « d'accord », « vas-y » \
ou toute réponse qui ne dit PAS clairement laquelle → « oui » NE SIGNIFIE \
JAMAIS « les deux ». Tu DOIS répondre par une COURTE question pour savoir \
laquelle, et NE PAS donner la réponse complète tout de suite. \
Exemple obligatoire — toi : « Voulez-vous l'eau, l'électricité, ou les \
deux ? » / la personne : « oui » / toi : « Parfait ! Vous parlez de l'eau, \
de l'électricité, ou des deux ? ». \
Tu ne traites plusieurs options QUE si la personne le dit EXPLICITEMENT \
(« les deux », « tout », « peu importe », « je veux tout savoir »).
7. PROACTIVITÉ LÉGÈRE : quand c'est utile, termine par UNE seule suggestion \
courte liée à sa situation (abonnement eau → proposer l'électricité ; \
paiement → espace client...). Une seule, brève, jamais inventée. Aucune \
suggestion après un refus hors-sujet ni après une question de clarification.
8. MESSAGE INCOMPRÉHENSIBLE (suite de lettres sans aucun sens : « asdf », \
« iam », « dbqibd »...) : ne cherche pas et ne devine pas. Réponds simplement : \
« Je n'ai pas bien compris votre message 🤔 Pouvez-vous reformuler ? »

INFORMATIONS DISPONIBLES :
{context}"""

app = FastAPI(title="Service RAG Amendis")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chargés une seule fois au démarrage du service
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

# ---------------------------------------------------------------------------
# RECHERCHE HYBRIDE : deux approches complémentaires fusionnées.
#   • Vectorielle (MMR)  : trouve par le SENS (paraphrases, synonymes) —
#     forte quand la formulation diffère du texte.
#   • BM25 (mots-clés)   : trouve par les MOTS EXACTS (noms propres, chiffres,
#     « Martil », un numéro...) — rattrape ce que l'embedding rate sur les
#     termes rares. C'est le correctif au problème « nom d'agence noyé ».
# L'EnsembleRetriever fusionne les deux classements (Reciprocal Rank Fusion).
# BM25 est quasi gratuit en mémoire (pas de modèle, juste un index de mots).
# ---------------------------------------------------------------------------
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

from rag_service.ingest import build_chunks

_vector_retriever = vectorstore.as_retriever(
    search_type="mmr", search_kwargs={"k": 6, "fetch_k": 25}
)
_bm25_retriever = BM25Retriever.from_documents(build_chunks())
_bm25_retriever.k = 6
retriever = EnsembleRetriever(
    retrievers=[_bm25_retriever, _vector_retriever], weights=[0.5, 0.5]
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

    # max_retries=0 : en cas de limite Groq, on ÉCHOUE VITE et on bascule sur
    # le modèle suivant, au lieu de réessayer 2 fois avec attente (~5-8 s).
    LLMS.append((f"groq/{GROQ_MODEL}",
                 ChatGroq(model=GROQ_MODEL, temperature=0, max_retries=0)))
    LLMS.append(("groq/openai/gpt-oss-20b",
                 ChatGroq(model="openai/gpt-oss-20b", temperature=0,
                          max_retries=0)))
if HAS_OLLAMA:
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


def generer_stream(template, variables: dict):
    """Comme generer(), mais renvoie les tokens AU FUR ET À MESURE (streaming).
    Essaie la chaîne de secours : on stream le premier modèle qui démarre."""
    for _, modele in LLMS:
        try:
            flux = (template | modele).stream(variables)
            premier = next(flux)          # peut lever si le modèle échoue
            yield premier.content
            for chunk in flux:
                yield chunk.content
            return
        except Exception:
            continue  # ce modèle a échoué → on tente le suivant
    yield ("Le service est momentanément surchargé. "
           "Merci de réessayer dans quelques instants.")
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
    ("system", "À partir de l'historique, reformule le DERNIER message de "
               "l'utilisateur en UNE question autonome et complète sur "
               "Amendis. Règles :\n"
               "- S'il répond à une suggestion (« oui », « les deux », « le "
               "premier »...), reprends le contenu de cette suggestion.\n"
               "- S'il CORRIGE ou PRÉCISE le sujet d'une de ses questions "
               "précédentes (« je parle de X », « non plutôt Y », « pour "
               "Z »...), garde l'INTENTION de sa question précédente mais "
               "applique-la au nouveau sujet. Exemple : précédemment "
               "« comment le télécharger ? », puis « je parle du service "
               "Amendis Info » → « comment obtenir le service Amendis Info ? ».\n"
               "- S'il est déjà autonome, renvoie-le tel quel.\n"
               "Réponds UNIQUEMENT par la question reformulée, sans commentaire."),
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


def _preparer(q: Question) -> tuple[str, str]:
    """Étapes communes (rapides) avant la génération : historique de
    l'utilisateur + recherche des extraits. Renvoie (contexte, historique)."""
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
    return context, history


@app.post("/ask")
def ask(q: Question) -> dict:
    context, history = _preparer(q)
    # generer() essaie 70b → 8b → Ollama jusqu'à obtenir une réponse
    result = generer(
        prompt, {"context": context, "history": history, "question": q.question}
    )
    enregistrer_echange(q.user_id, q.question, result.content)
    return {"answer": result.content}


# ---------------------------------------------------------------------------
# Filtre de politesses : les salutations, remerciements et au revoir reçoivent
# une réponse FIXE, instantanée, SANS appeler le LLM (gratuit, rapide, pas de
# consommation de quota). Tout le reste (y compris le charabia) passe au RAG,
# dont le prompt sait demander une reformulation si le message n'a pas de sens.
# ---------------------------------------------------------------------------
POLITESSES = {
    "saluer": ({"bonjour", "salut", "bonsoir", "hello", "hey", "coucou",
                "salam", "slm", "cc", "yo", "bjr"},
               "Bonjour ! 👋 Je suis l'assistant virtuel d'Amendis. Je peux "
               "vous renseigner sur vos factures, abonnements, fuites, agences… "
               "Comment puis-je vous aider ?"),
    "remercier": ({"merci", "merci beaucoup", "mrc", "thanks", "thank you",
                   "je vous remercie", "merci bien"},
                  "Je vous en prie ! Puis-je vous aider pour autre chose ?"),
    "au_revoir": ({"au revoir", "bye", "à bientôt", "a bientot", "ciao",
                   "bonne journée", "bonne journee", "adieu", "aurevoir"},
                  "Merci d'avoir utilisé l'assistance Amendis. À bientôt ! 👋"),
}


def politesse(message: str) -> str | None:
    """Réponse fixe si le message EST une simple politesse, sinon None."""
    m = message.strip().lower().strip("!?.,;: ")
    for _, (mots, reponse) in POLITESSES.items():
        if m in mots:
            return reponse
    return None


@app.post("/chat")
def chat(q: Question) -> dict:
    """Point d'entrée non-streaming (compatibilité). Politesse instantanée,
    sinon délègue à la logique RAG complète."""
    reponse_fixe = politesse(q.question)
    if reponse_fixe:
        return {"answer": reponse_fixe}
    return ask(q)


@app.post("/chat_stream")
def chat_stream(q: Question):
    """Point d'entrée STREAMING utilisé par le front : renvoie la réponse
    token par token (StreamingResponse). Les premiers mots arrivent en ~1 s."""
    reponse_fixe = politesse(q.question)
    if reponse_fixe:
        # politesse : réponse immédiate en un seul morceau
        return StreamingResponse(iter([reponse_fixe]), media_type="text/plain")

    context, history = _preparer(q)

    def flux():
        morceaux = []
        for token in generer_stream(
            prompt, {"context": context, "history": history, "question": q.question}
        ):
            morceaux.append(token)
            yield token
        # une fois la réponse complète streamée, on la mémorise
        enregistrer_echange(q.user_id, q.question, "".join(morceaux))

    return StreamingResponse(flux(), media_type="text/plain")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": LLM_INFO}
