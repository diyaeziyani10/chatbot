"""Front-end Streamlit — interface de chat du PoC.

Communique avec le serveur Rasa via son API REST :
POST http://localhost:5005/webhooks/rest/webhook

Usage : streamlit run frontend/app.py
"""
import uuid

import requests
import streamlit as st

RASA_URL = "http://localhost:5005/webhooks/rest/webhook"

SUJETS_FREQUENTS = [
    "Comment payer ma facture ?",
    "Comment consulter ma consommation ?",
    "Que faire en cas de fuite d'eau ?",
    "Comment résilier mon contrat ?",
]

st.set_page_config(page_title="Assistant Amendis", page_icon="💧")
st.title("💧⚡ Assistant virtuel Amendis")
st.caption("PoC — assistance client eau & électricité, disponible 24h/24")

# Identifiant de session pour que Rasa suive la conversation
if "sender_id" not in st.session_state:
    st.session_state.sender_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Bonjour ! 👋 Je suis l'assistant virtuel d'Amendis. "
                       "Posez-moi votre question ou choisissez un sujet fréquent.",
        }
    ]


def send_to_rasa(text: str) -> list[str]:
    """Envoie le message de l'utilisateur à Rasa et renvoie ses réponses."""
    try:
        resp = requests.post(
            RASA_URL,
            json={"sender": st.session_state.sender_id, "message": text},
            timeout=90,
        )
        resp.raise_for_status()
        replies = [m["text"] for m in resp.json() if "text" in m]
        return replies or ["Désolé, je n'ai pas compris. Pouvez-vous reformuler ?"]
    except requests.RequestException:
        return ["⚠️ Le serveur du chatbot est injoignable. "
                "Vérifiez que Rasa est bien lancé (rasa run --enable-api)."]


def process(text: str) -> None:
    st.session_state.messages.append({"role": "user", "content": text})
    for reply in send_to_rasa(text):
        st.session_state.messages.append({"role": "assistant", "content": reply})


# Accueil automatisé : suggestion de sujets fréquents (cahier des charges 3.1.1)
with st.sidebar:
    st.subheader("Sujets fréquents")
    for sujet in SUJETS_FREQUENTS:
        if st.button(sujet, use_container_width=True):
            process(sujet)

# Historique de la conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Saisie libre
if user_input := st.chat_input("Écrivez votre message..."):
    process(user_input)
    st.rerun()
