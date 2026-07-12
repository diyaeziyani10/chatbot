"""Custom Actions Rasa — logique métier du chatbot Amendis.

Sécurité (cahier des charges, section 4) : les données clients (contrats,
factures) sont lues ici, en local, via SQLite. Elles ne sont JAMAIS envoyées
au LLM. Seul le texte des questions hors scénario part vers le service RAG.
"""
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Text

import requests
from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

# Chemin de la base de simulation (database/amendis.db à la racine du projet)
DB_PATH = Path(__file__).resolve().parents[2] / "database" / "amendis.db"

# Service RAG local (rag_service/rag_api.py)
RAG_URL = "http://localhost:8000/ask"


def _query_db(sql: str, params: tuple = ()) -> List[tuple]:
    """Exécute une requête sur la base SQLite locale."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(sql, params).fetchall()


class ValidateFactureForm(FormValidationAction):
    """Validation du numéro de contrat saisi dans le formulaire."""

    def name(self) -> Text:
        return "validate_facture_form"

    def validate_numero_contrat(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Format attendu : 6 chiffres commençant par 5 (ex : 500123)
        value = str(slot_value).strip()
        if re.fullmatch(r"5\d{5}", value):
            return {"numero_contrat": value}
        dispatcher.utter_message(
            text="Ce numéro ne semble pas valide. Un numéro de contrat "
                 "Amendis comporte 6 chiffres et commence par 5 (ex : 500123)."
        )
        return {"numero_contrat": None}


class ActionConsulterFacture(Action):
    """Scénario strict : interrogation de la base SQLite (simulation SI)."""

    def name(self) -> Text:
        return "action_consulter_facture"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        numero = tracker.get_slot("numero_contrat")

        rows = _query_db(
            """
            SELECT c.nom, f.mois, f.montant, f.statut
            FROM factures f
            JOIN clients c ON c.numero_contrat = f.numero_contrat
            WHERE f.numero_contrat = ?
            ORDER BY f.id DESC
            LIMIT 1
            """,
            (numero,),
        )

        if not rows:
            dispatcher.utter_message(
                text=f"Aucun contrat trouvé avec le numéro {numero}. "
                     "Vérifiez le numéro sur votre facture et réessayez."
            )
        else:
            nom, mois, montant, statut = rows[0]
            statut_txt = "✅ payée" if statut == "payee" else "⏳ en attente de paiement"
            dispatcher.utter_message(
                text=f"📄 Contrat {numero} ({nom})\n"
                     f"Dernière facture — {mois} : {montant:.2f} DH ({statut_txt}).\n"
                     "Vous pouvez la régler sur https://www.amendisclient.ma"
            )

        # On vide le slot pour permettre une nouvelle consultation
        return [SlotSet("numero_contrat", None)]


class ActionSignalerFuite(Action):
    """Enregistre un signalement d'incident dans la base locale."""

    def name(self) -> Text:
        return "action_signaler_fuite"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        description = tracker.latest_message.get("text", "")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO incidents (description, date_signalement) VALUES (?, ?)",
                (description, date),
            )
            reference = cur.lastrowid

        dispatcher.utter_message(
            text=f"🚨 Votre signalement a bien été enregistré (référence n°{reference}).\n"
                 "Une équipe technique Amendis sera dépêchée dans les meilleurs délais. "
                 "En cas d'urgence, appelez le centre d'appel : 05 39 32 88 88."
        )
        return []


class ActionRagFallback(Action):
    """Fallback : question hors scénario → service RAG (documentation Amendis).

    Seul le texte de la question est transmis. Le service répond uniquement
    à partir du corpus scrapé sur www.amendis.ma (zéro hallucination).
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
            resp = requests.post(RAG_URL, json={"question": question}, timeout=60)
            resp.raise_for_status()
            answer = resp.json().get("answer", "").strip()
            if answer:
                dispatcher.utter_message(text=answer)
            else:
                dispatcher.utter_message(response="utter_hors_sujet")
        except requests.RequestException:
            dispatcher.utter_message(
                text="Le service de documentation est momentanément indisponible. "
                     "Veuillez réessayer dans quelques instants."
            )
        return []
