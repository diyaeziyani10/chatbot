"""Custom Actions Rasa — chatbot Amendis.

Architecture 100 % documentaire : aucune donnée client, aucune base SQLite.
La seule action interroge le service RAG, qui répond uniquement à partir
du corpus scrapé sur www.amendis.ma (zéro hallucination).
"""
from typing import Any, Dict, List, Text

import requests
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

# Service RAG local (rag_service/rag_api.py)
RAG_URL = "http://localhost:8000/ask"


class ActionRagFallback(Action):
    """Fallback : question hors politesse → service RAG (documentation Amendis).

    Seul le texte de la question est transmis. Le service répond uniquement
    à partir du corpus scrapé sur www.amendis.ma.
    """

    def name(self) -> Text:
        return "action_rag_fallback"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        question = tracker.latest_message.get("text", "")
        try:
            # sender_id = identifiant choisi par l'utilisateur dans le front
            # (ou un UUID anonyme) → permet au RAG de retrouver sa mémoire.
            resp = requests.post(
                RAG_URL,
                json={"question": question, "user_id": tracker.sender_id},
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "").strip()
            if answer:
                # Réponse directe, sans liens (conversation plus naturelle).
                dispatcher.utter_message(text=answer)
            else:
                dispatcher.utter_message(
                    text="Je n'ai pas trouvé cette information dans la documentation "
                         "Amendis. Vous pouvez reformuler ou contacter le service client."
                )
        except requests.RequestException:
            dispatcher.utter_message(
                text="Le service de documentation est momentanément indisponible. "
                     "Veuillez réessayer dans quelques instants."
            )
        return []
