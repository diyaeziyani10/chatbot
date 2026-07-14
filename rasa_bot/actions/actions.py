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
            resp = requests.post(RAG_URL, json={"question": question}, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "").strip()
            sources = [s for s in data.get("sources", []) if s][:3]
            if answer:
                # Traçabilité : on joint les pages amendis.ma utilisées,
                # sauf si le RAG n'a rien trouvé (sources non pertinentes).
                if sources and "je n'ai pas trouvé" not in answer.lower():
                    liens = "\n".join(f"• {s}" for s in sources)
                    answer += f"\n\n🔗 Pour en savoir plus :\n{liens}"
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
