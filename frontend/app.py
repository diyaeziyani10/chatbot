"""Front-end Streamlit — implémentation du design « 1b · Marketing + widget »
(projet Claude Design : Amendis Chatbot Landing).

Page d'accueil marketing avec le chat fonctionnel intégré dans le widget
de droite. Communique avec Rasa via son API REST :
POST http://localhost:5005/webhooks/rest/webhook

Usage : streamlit run frontend/app.py
"""
import base64
import codecs
import html as html_lib
import re
import uuid
from pathlib import Path

import requests
import streamlit as st

# Le front parle DIRECTEMENT au service RAG (Rasa a été retiré : son rôle
# résiduel — politesses, charabia, routage — est désormais assuré par le
# RAG lui-même via l'endpoint /chat). Gain : ~3-4 s de latence en moins.
RAG_URL = "http://localhost:8000/chat"
RAG_STREAM_URL = "http://localhost:8000/chat_stream"

# Images du dossier frontend/assets (fichiers remplaçables par les vôtres)
ASSETS_DIR = Path(__file__).parent / "assets"

SUJETS_FREQUENTS = [
    "Comment payer ma facture ?",
    "Comment consulter ma consommation ?",
    "Que faire en cas de fuite d'eau ?",
    "Comment résilier mon contrat ?",
]

MESSAGE_ACCUEIL = ("Bonjour 👋 Je suis l'assistant virtuel d'Amendis. "
                   "Posez-moi votre question ou choisissez un sujet.")


def image_base64(path: Path) -> str:
    """Encode une image en base64 pour l'intégrer directement dans le HTML."""
    return base64.b64encode(path.read_bytes()).decode()


# ---------------------------------------------------------------------------
# Logique de conversation (inchangée : Rasa fait tout le travail)
# ---------------------------------------------------------------------------
if "sender_id" not in st.session_state:
    st.session_state.sender_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": MESSAGE_ACCUEIL}]
if "pending" not in st.session_state:
    st.session_state.pending = None  # question en attente de réponse du RAG


def sender_id() -> str:
    """Identifiant de conversation : le nom saisi par l'utilisateur si fourni
    (→ le bot le reconnaît d'une session à l'autre), sinon un UUID anonyme."""
    nom = (st.session_state.get("user_field") or "").strip()
    return nom.lower() if nom else st.session_state.sender_id


def stream_from_bot(text: str):
    """Interroge le service RAG en STREAMING (/chat_stream) et renvoie les
    tokens au fur et à mesure. Un décodeur UTF-8 incrémental évite de couper
    un caractère accentué (é, è...) à cheval sur deux morceaux réseau."""
    try:
        with requests.post(
            RAG_STREAM_URL,
            json={"question": text, "user_id": sender_id()},
            stream=True, timeout=200,
        ) as resp:
            resp.raise_for_status()
            decodeur = codecs.getincrementaldecoder("utf-8")()
            for morceau in resp.iter_content(chunk_size=None):
                if morceau:
                    texte = decodeur.decode(morceau)
                    if texte:
                        yield texte
    except requests.RequestException:
        yield ("⚠️ Le service est injoignable. Vérifiez que le service RAG "
               "est lancé (uvicorn rag_service.rag_api:app --port 8000).")


def queue_message(text: str) -> None:
    """Affiche la question TOUT DE SUITE et marque une réponse à traiter.
    L'appel (lent) au RAG est fait ensuite, dans un second passage, pour que
    la question de l'utilisateur apparaisse avant la réponse."""
    text = (text or "").strip()
    if text:
        st.session_state.messages.append({"role": "user", "content": text})
        st.session_state.pending = text


def on_send() -> None:
    """Callback du bouton d'envoi (exécuté AVANT le rafraîchissement)."""
    queue_message(st.session_state.get("chat_box", ""))


# ---------------------------------------------------------------------------
# Mise en page — design « 1b » : rouge Amendis #E2001A,
# polices Space Grotesk (titres) + Public Sans (texte)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Assistant virtuel Amendis", page_icon="💧",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

/* Cache le bandeau/menu Streamlit pour un rendu pleine page */
#MainMenu, header, footer {visibility: hidden;}
.block-container {max-width: 1240px; padding-top: 28px; font-family: 'Public Sans', system-ui, sans-serif;}

/* --- En-tête --- */
.am-nav {display:flex; align-items:center; justify-content:space-between;
  padding: 6px 4px 20px; border-bottom:1px solid #eef0f2; margin-bottom: 34px;}
.am-amendis {height: 52px;}
.am-opere {display:flex; align-items:center; gap:10px; font-style:italic;
  font-size:15px; color:#6d6e71;}
.am-veolia-logo {height: 30px;}

/* --- Héro gauche --- */
.am-badge {display:inline-flex; align-items:center; gap:9px; background:#fff5f4;
  color:#E2001A; font-size:13px; font-weight:600; padding:7px 15px; border-radius:999px;}
.am-h1 {font-family:'Space Grotesk',sans-serif; font-size:50px; line-height:1.05;
  font-weight:700; color:#26262b; margin:22px 0 0; letter-spacing:-1px;}
.am-h1 .rouge {color:#E2001A;}
.am-lead {font-size:18px; line-height:1.6; color:#61626a; margin:20px 0 0; max-width:460px;}
.am-stats {display:flex; gap:26px; margin:38px 0 0;}
.am-stats .sep {width:1px; background:#eef0f2;}
.am-stat-num {font-family:'Space Grotesk',sans-serif; font-size:26px; font-weight:700; color:#26262b;}
.am-stat-lab {font-size:13px; color:#8a8b91;}

/* --- Widget de chat (colonne droite) --- */
.am-widget-top {display:flex; align-items:center; gap:12px; padding:16px 18px;
  background:#fff; border:1px solid #edeef1; border-bottom:none; border-radius:16px 16px 0 0;}
.am-widget-top .bot {width:40px; height:40px; border-radius:11px; background:#E2001A;
  display:flex; align-items:center; justify-content:center;}
.am-widget-title {font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:15px; color:#26262b; line-height:1.2;}
.am-enligne {font-size:12px; color:#1db954; display:flex; align-items:center; gap:5px;}
.am-enligne .pt {width:6px; height:6px; border-radius:50%; background:#1db954;}
.am-strip {height:3px; background:linear-gradient(90deg,#2b7de9,#22b8cf,#8ac926,#f4a300,#E2001A);
  border-left:1px solid #edeef1; border-right:1px solid #edeef1;}
/* column-reverse : le fil défile DANS la boîte (hauteur fixe) et reste collé
   en bas → la dernière question/réponse est toujours visible sans agrandir la page. */
.am-msgs {display:flex; flex-direction:column-reverse; gap:12px;
  height:360px; overflow-y:auto; padding:20px 18px; background:#fbfbfc;
  border-left:1px solid #edeef1; border-right:1px solid #edeef1;}
/* Indicateur « en train d'écrire » (trois points animés) */
.am-typing {align-self:flex-start; display:flex; align-items:center; gap:5px;
  background:#fff; border:1px solid #eef0f2; border-radius:14px; padding:14px 16px;}
.am-typing span {width:7px; height:7px; border-radius:50%; background:#c9cace;
  animation:amPulse 1.2s ease-in-out infinite;}
.am-typing span:nth-child(2){animation-delay:.2s;}
.am-typing span:nth-child(3){animation-delay:.4s;}
@keyframes amPulse{0%,100%{opacity:.35;transform:scale(1);}50%{opacity:1;transform:scale(1.35);}}
/* Masque l'indication « Press Enter to submit form » sous le champ */
[data-testid="InputInstructions"]{display:none;}
.am-bot-bulle {align-self:flex-start; max-width:85%; background:#fff; border:1px solid #eef0f2;
  border-radius:4px 14px 14px 14px; padding:12px 14px; font-size:13.5px; line-height:1.5; color:#3a3b41;
  overflow-wrap:anywhere;}
.am-user-bulle {align-self:flex-end; max-width:85%; background:#E2001A; color:#fff;
  border-radius:14px 4px 14px 14px; padding:12px 14px; font-size:13.5px; line-height:1.5;
  overflow-wrap:anywhere;}
.am-bot-bulle a {color:#E2001A; word-break:break-all;}
.am-input-wrap {border:1px solid #edeef1; border-top:1px solid #f1f2f4;
  border-radius:0 0 16px 16px; background:#fff; padding:6px 10px 2px;}

/* Champ + bouton d'envoi du formulaire */
[data-testid="stForm"] {border:none; padding:0;}
.am-input-wrap [data-testid="stTextInput"] input {border:none; background:#fff; font-size:14px;}
.am-input-wrap .stButton button, .am-input-wrap [data-testid="stFormSubmitButton"] button {
  background:#E2001A; color:#fff; border:none; border-radius:9px; font-size:16px; min-height:38px;}

/* Chips sujets fréquents */
div[data-testid="column"] .stButton > button {
  width:100%; background:#f6f7f8; color:#26262b; border:1px solid #e6e7ea;
  border-radius:999px; font-size:13px; font-weight:500; padding:8px 10px;}
div[data-testid="column"] .stButton > button:hover {border-color:#E2001A; color:#E2001A; background:#fff;}

/* --- Bandeau fonctionnalités --- */
.am-feats {display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:44px;}
.am-feat {display:flex; gap:13px; align-items:flex-start; padding:18px;
  border-radius:14px; background:#fafbfc; border:1px solid #eef0f2;}
.am-feat .ic {width:34px; height:34px; flex:none; border-radius:9px; background:#fff5f4;
  display:flex; align-items:center; justify-content:center;}
.am-feat-t {font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:14.5px; color:#26262b;}
.am-feat-d {font-size:12.5px; color:#7a7b82; line-height:1.45; margin-top:3px;}
</style>
""", unsafe_allow_html=True)

# --- En-tête : logo Amendis + « opéré par VEOLIA » ---
logo = ASSETS_DIR / "logo.webp"
veolia = ASSETS_DIR / "veolia.webp"
st.markdown(f"""
<div class="am-nav">
  <img class="am-amendis" src="data:image/webp;base64,{image_base64(logo)}" alt="Amendis"/>
  <span class="am-opere">opéré par
    <img class="am-veolia-logo" src="data:image/webp;base64,{image_base64(veolia)}" alt="Veolia"/>
  </span>
</div>
""", unsafe_allow_html=True)

# --- Héro : marketing à gauche, widget de chat fonctionnel à droite ---
col_gauche, col_droite = st.columns([1.05, 0.9], gap="large")

with col_gauche:
    st.markdown("""
    <span class="am-badge">Nouveau · Assistant virtuel Amendis</span>
    <h1 class="am-h1">L'aide dont vous avez besoin, <span class="rouge">sans attendre.</span></h1>
    <p class="am-lead">Notre assistant répond à vos questions sur l'eau, l'électricité
    et vos démarches — instantanément, 24h/24 et 7j/7, en français.</p>
    <div class="am-stats">
      <div><div class="am-stat-num">24/7</div><div class="am-stat-lab">Toujours disponible</div></div>
      <div class="sep"></div>
      <div><div class="am-stat-num">&lt; 10 s</div><div class="am-stat-lab">Temps de réponse</div></div>
      <div class="sep"></div>
      <div><div class="am-stat-num">FR</div><div class="am-stat-lab">En langage naturel</div></div>
    </div>
    """, unsafe_allow_html=True)

with col_droite:
    # En-tête du widget (avatar robot + statut « En ligne »)
    st.markdown("""
    <div class="am-widget-top">
      <span class="bot"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><rect x="4" y="8" width="16" height="11" rx="3"></rect><circle cx="9" cy="13.5" r="1.3" fill="#fff" stroke="none"></circle><circle cx="15" cy="13.5" r="1.3" fill="#fff" stroke="none"></circle><line x1="12" y1="4" x2="12" y2="8"></line><circle cx="12" cy="3" r="1.4" fill="#fff" stroke="none"></circle></svg></span>
      <div><div class="am-widget-title">Assistant virtuel Amendis</div>
      <div class="am-enligne"><span class="pt"></span>En ligne</div></div>
    </div>
    <div class="am-strip"></div>
    """, unsafe_allow_html=True)

    # Fil de conversation (bulles construites depuis l'historique)
    def bulle(msg: dict) -> str:
        texte = html_lib.escape(msg["content"]).replace("\n", "<br>")
        texte = re.sub(r"(https?://[^\s<]+)",
                       r'<a href="\1" target="_blank">\1</a>', texte)
        classe = "am-user-bulle" if msg["role"] == "user" else "am-bot-bulle"
        return f'<div class="{classe}">{texte}</div>'

    # Ordre inversé (column-reverse CSS : le 1er élément du HTML s'affiche EN BAS).
    def messages_html(streaming: str | None = None) -> str:
        parts = []
        if streaming is not None:      # réponse en cours d'écriture, tout en bas
            parts.append(bulle({"role": "assistant", "content": streaming}))
        elif st.session_state.pending:  # « … » animé en attendant le 1er mot
            parts.append('<div class="am-typing"><span></span><span></span><span></span></div>')
        parts.extend(bulle(m) for m in reversed(st.session_state.messages))
        return f'<div class="am-msgs">{"".join(parts)}</div>'

    # Placeholder : permet de mettre à jour le fil EN DIRECT pendant le streaming.
    msgs_ph = st.empty()
    msgs_ph.markdown(messages_html(), unsafe_allow_html=True)

    # Zone de saisie (le callback met à jour l'historique AVANT le re-rendu)
    st.markdown('<div class="am-input-wrap">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True, border=False):
        c_txt, c_btn = st.columns([5, 1])
        c_txt.text_input("message", key="chat_box", label_visibility="collapsed",
                         placeholder="Écrivez votre message…")
        c_btn.form_submit_button("↑", on_click=on_send, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Sujets fréquents (accueil automatisé — cahier des charges 3.1.1)
    chip_cols = st.columns(2)
    for i, sujet in enumerate(SUJETS_FREQUENTS):
        chip_cols[i % 2].button(sujet, on_click=queue_message, args=(sujet,))

    # Identification facultative → active la mémoire persistante du bot
    # (il se souviendra des échanges d'une session à l'autre)
    st.text_input(
        "🪪 Votre nom ou n° de client — pour que l'assistant se souvienne de vous",
        key="user_field",
        placeholder="optionnel, ex : karim123",
    )

# --- Bandeau des fonctionnalités (4 cartes, comme le design) ---
st.markdown("""
<div class="am-feats">
  <div class="am-feat">
    <span class="ic"><svg width="17" height="17" viewBox="0 0 20 20" fill="none" stroke="#E2001A" stroke-width="1.6"><rect x="4" y="2.5" width="12" height="15" rx="1.5"></rect><line x1="7" y1="7" x2="13" y2="7"></line><line x1="7" y1="10" x2="13" y2="10"></line></svg></span>
    <div><div class="am-feat-t">Factures &amp; paiements</div>
    <div class="am-feat-d">Consulter et régler vos factures.</div></div>
  </div>
  <div class="am-feat">
    <span class="ic"><svg width="17" height="17" viewBox="0 0 20 20" fill="none" stroke="#E2001A" stroke-width="1.6"><rect x="3" y="11" width="3.4" height="6" rx="1"></rect><rect x="8.3" y="7" width="3.4" height="10" rx="1"></rect><rect x="13.6" y="3.5" width="3.4" height="13.5" rx="1"></rect></svg></span>
    <div><div class="am-feat-t">Consommation</div>
    <div class="am-feat-d">Suivre vos relevés de compteur.</div></div>
  </div>
  <div class="am-feat">
    <span class="ic"><svg width="17" height="17" viewBox="0 0 20 20" fill="none" stroke="#E2001A" stroke-width="1.6"><circle cx="10" cy="12" r="5"></circle><path d="M10 2.5 C10 5.5 14 6.5 14 9.5" opacity=".55"></path></svg></span>
    <div><div class="am-feat-t">Fuites &amp; incidents</div>
    <div class="am-feat-d">Que faire en cas de fuite.</div></div>
  </div>
  <div class="am-feat">
    <span class="ic"><svg width="17" height="17" viewBox="0 0 20 20" fill="none" stroke="#E2001A" stroke-width="1.6"><rect x="4" y="3" width="12" height="14" rx="1.5"></rect><path d="M7 11.5 l2 2 l4 -4.5"></path></svg></span>
    <div><div class="am-feat-t">Contrats &amp; démarches</div>
    <div class="am-feat-d">Souscription et résiliation.</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

# --- Traitement en STREAMING : la question est déjà affichée (avec le « … »
# animé) ; on interroge le service RAG et on écrit la réponse mot par mot
# DANS le fil, en direct, sans attendre la réponse complète.
if st.session_state.pending:
    question = st.session_state.pending
    st.session_state.pending = None
    reponse = ""
    for token in stream_from_bot(question):
        reponse += token
        msgs_ph.markdown(messages_html(streaming=reponse), unsafe_allow_html=True)
    # Réponse complète : on la fige dans l'historique
    st.session_state.messages.append({"role": "assistant", "content": reponse})
    msgs_ph.markdown(messages_html(), unsafe_allow_html=True)
