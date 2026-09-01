"""Front-end Streamlit optimisé pour Streamlit Community Cloud (sans API).

Ce fichier fusionne l'interface (app.py) et la logique RAG (rag_api.py)
en un seul processus. Il ne nécessite pas de lancer FastAPI ni uvicorn.
Parfait pour l'hébergement gratuit sur share.streamlit.io.
"""
import base64
import html as html_lib
import re
import uuid
from pathlib import Path
import streamlit as st

# On importe directement la logique RAG !
from rag_service.rag_api import politesse, _preparer, generer_stream, prompt, enregistrer_echange, Question

import sys

if getattr(sys, 'frozen', False):
    ASSETS_DIR = Path(sys._MEIPASS) / "frontend" / "assets"
else:
    ASSETS_DIR = Path(__file__).parent / "frontend" / "assets"

SUJETS_FREQUENTS = [
    "Comment payer ma facture ?",
    "Comment consulter ma consommation ?",
    "Que faire en cas de fuite d'eau ?",
    "Comment résilier mon contrat ?",
]

MESSAGE_ACCUEIL = ("Bonjour 👋 Je suis l'assistant virtuel d'Amendis. "
                   "Posez-moi votre question ou choisissez un sujet.")


def image_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


# ---------------------------------------------------------------------------
# État de la conversation (mémoire de session Streamlit)
# ---------------------------------------------------------------------------
if "sender_id" not in st.session_state:
    st.session_state.sender_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": MESSAGE_ACCUEIL}]
if "pending" not in st.session_state:
    st.session_state.pending = None  # question en attente de réponse


def sender_id() -> str:
    nom = (st.session_state.get("user_field") or "").strip()
    return nom.lower() if nom else st.session_state.sender_id


def stream_from_bot(text: str):
    """Génère la réponse directement depuis le modèle (sans HTTP)."""
    q = Question(question=text, user_id=sender_id())
    
    # 1. Vérifie si c'est une formule de politesse
    reponse_fixe = politesse(q.question)
    if reponse_fixe:
        yield reponse_fixe
        return
        
    # 2. Prépare le contexte (recherche dans ChromaDB)
    context, history = _preparer(q)
    
    # 3. Génère la réponse token par token
    morceaux = []
    for token in generer_stream(
        prompt, {"context": context, "history": history, "question": q.question}
    ):
        morceaux.append(token)
        yield token
        
    # 4. Enregistre l'échange une fois terminé
    enregistrer_echange(q.user_id, q.question, "".join(morceaux))


def queue_message(text: str) -> None:
    text = (text or "").strip()
    if text:
        st.session_state.messages.append({"role": "user", "content": text})
        st.session_state.pending = text


def on_send() -> None:
    queue_message(st.session_state.get("chat_box", ""))


# ---------------------------------------------------------------------------
# Mise en page — design « 1b » : rouge Amendis #E2001A
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Assistant virtuel Amendis", page_icon="💧",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

#MainMenu, header, footer {visibility: hidden;}
.block-container {max-width: 1240px; padding-top: 28px; font-family: 'Public Sans', system-ui, sans-serif;}

.am-nav {display:flex; align-items:center; justify-content:space-between;
  padding: 6px 4px 20px; border-bottom:1px solid #eef0f2; margin-bottom: 34px;}
.am-amendis {height: 52px;}
.am-opere {display:flex; align-items:center; gap:10px; font-style:italic;
  font-size:15px; color:#6d6e71;}
.am-veolia-logo {height: 30px;}

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

.am-widget-top {display:flex; align-items:center; gap:12px; padding:16px 18px;
  background:#fff; border:1px solid #edeef1; border-bottom:none; border-radius:16px 16px 0 0;}
.am-widget-top .bot {width:40px; height:40px; border-radius:11px; background:#E2001A;
  display:flex; align-items:center; justify-content:center;}
.am-widget-title {font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:15px; color:#26262b; line-height:1.2;}
.am-enligne {font-size:12px; color:#1db954; display:flex; align-items:center; gap:5px;}
.am-enligne .pt {width:6px; height:6px; border-radius:50%; background:#1db954;}
.am-strip {height:3px; background:linear-gradient(90deg,#2b7de9,#22b8cf,#8ac926,#f4a300,#E2001A);
  border-left:1px solid #edeef1; border-right:1px solid #edeef1;}
.am-msgs {display:flex; flex-direction:column-reverse; gap:12px;
  height:360px; overflow-y:auto; padding:20px 18px; background:#fbfbfc;
  border-left:1px solid #edeef1; border-right:1px solid #edeef1;}
.am-typing {align-self:flex-start; display:flex; align-items:center; gap:5px;
  background:#fff; border:1px solid #eef0f2; border-radius:14px; padding:14px 16px;}
.am-typing span {width:7px; height:7px; border-radius:50%; background:#c9cace;
  animation:amPulse 1.2s ease-in-out infinite;}
.am-typing span:nth-child(2){animation-delay:.2s;}
.am-typing span:nth-child(3){animation-delay:.4s;}
@keyframes amPulse{0%,100%{opacity:.35;transform:scale(1);}50%{opacity:1;transform:scale(1.35);}}
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

[data-testid="stForm"] {border:none; padding:0;}
.am-input-wrap [data-testid="stTextInput"] input {border:none; background:#fff; font-size:14px;}
.am-input-wrap .stButton button, .am-input-wrap [data-testid="stFormSubmitButton"] button {
  background:#E2001A; color:#fff; border:none; border-radius:9px; font-size:16px; min-height:38px;}

div[data-testid="column"] .stButton > button {
  width:100%; background:#f6f7f8; color:#26262b; border:1px solid #e6e7ea;
  border-radius:999px; font-size:13px; font-weight:500; padding:8px 10px;}
div[data-testid="column"] .stButton > button:hover {border-color:#E2001A; color:#E2001A; background:#fff;}

.am-feats {display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:44px;}
.am-feat {display:flex; gap:13px; align-items:flex-start; padding:18px;
  border-radius:14px; background:#fafbfc; border:1px solid #eef0f2;}
.am-feat .ic {width:34px; height:34px; flex:none; border-radius:9px; background:#fff5f4;
  display:flex; align-items:center; justify-content:center;}
.am-feat-t {font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:14.5px; color:#26262b;}
.am-feat-d {font-size:12.5px; color:#7a7b82; line-height:1.45; margin-top:3px;}
</style>
""", unsafe_allow_html=True)

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
    st.markdown("""
    <div class="am-widget-top">
      <span class="bot"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><rect x="4" y="8" width="16" height="11" rx="3"></rect><circle cx="9" cy="13.5" r="1.3" fill="#fff" stroke="none"></circle><circle cx="15" cy="13.5" r="1.3" fill="#fff" stroke="none"></circle><line x1="12" y1="4" x2="12" y2="8"></line><circle cx="12" cy="3" r="1.4" fill="#fff" stroke="none"></circle></svg></span>
      <div><div class="am-widget-title">Assistant virtuel Amendis</div>
      <div class="am-enligne"><span class="pt"></span>En ligne</div></div>
    </div>
    <div class="am-strip"></div>
    """, unsafe_allow_html=True)

    def bulle(msg: dict) -> str:
        texte = html_lib.escape(msg["content"]).replace("\n", "<br>")
        texte = re.sub(r"(https?://[^\s<]+)",
                       r'<a href="\1" target="_blank">\1</a>', texte)
        classe = "am-user-bulle" if msg["role"] == "user" else "am-bot-bulle"
        return f'<div class="{classe}">{texte}</div>'

    def messages_html(streaming: str | None = None) -> str:
        parts = []
        if streaming is not None:
            parts.append(bulle({"role": "assistant", "content": streaming}))
        elif st.session_state.pending:
            parts.append('<div class="am-typing"><span></span><span></span><span></span></div>')
        parts.extend(bulle(m) for m in reversed(st.session_state.messages))
        return f'<div class="am-msgs">{"".join(parts)}</div>'

    msgs_ph = st.empty()
    msgs_ph.markdown(messages_html(), unsafe_allow_html=True)

    st.markdown('<div class="am-input-wrap">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True, border=False):
        c_txt, c_btn = st.columns([5, 1])
        c_txt.text_input("message", key="chat_box", label_visibility="collapsed",
                         placeholder="Écrivez votre message…")
        c_btn.form_submit_button("↑", on_click=on_send, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    chip_cols = st.columns(2)
    for i, sujet in enumerate(SUJETS_FREQUENTS):
        chip_cols[i % 2].button(sujet, on_click=queue_message, args=(sujet,))

    st.text_input(
        "🪪 Votre nom ou n° de client — pour que l'assistant se souvienne de vous",
        key="user_field",
        placeholder="optionnel, ex : karim123",
    )

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

if st.session_state.pending:
    question = st.session_state.pending
    st.session_state.pending = None
    reponse = ""
    for token in stream_from_bot(question):
        reponse += token
        msgs_ph.markdown(messages_html(streaming=reponse), unsafe_allow_html=True)
    st.session_state.messages.append({"role": "assistant", "content": reponse})
    msgs_ph.markdown(messages_html(), unsafe_allow_html=True)
