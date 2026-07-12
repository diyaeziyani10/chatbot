"""Création et peuplement de la base SQLite de simulation (amendis.db).

Cette base imite le SI client d'Amendis (l'espace client amendisclient.ma) :
clients, contrats et factures fictifs, plus une table d'incidents alimentée
par le chatbot lors des signalements de fuite/panne.

Usage : python database/init_db.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "amendis.db"

SCHEMA = """
DROP TABLE IF EXISTS factures;
DROP TABLE IF EXISTS incidents;
DROP TABLE IF EXISTS clients;

CREATE TABLE clients (
    numero_contrat TEXT PRIMARY KEY,   -- 6 chiffres, commence par 5
    nom            TEXT NOT NULL,
    adresse        TEXT NOT NULL,
    type_service   TEXT NOT NULL       -- eau / electricite / eau+electricite
);

CREATE TABLE factures (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_contrat TEXT NOT NULL REFERENCES clients(numero_contrat),
    mois           TEXT NOT NULL,      -- ex : "juin 2026"
    montant        REAL NOT NULL,      -- en dirhams
    statut         TEXT NOT NULL       -- payee / impayee
);

CREATE TABLE incidents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_contrat   TEXT,             -- optionnel : signalement anonyme possible
    description      TEXT NOT NULL,
    date_signalement TEXT NOT NULL
);
"""

CLIENTS = [
    ("500123", "Diyae Ziyani",   "12 Av. Mohammed V, Tanger",   "eau+electricite"),
    ("500456", "Ahmed Alaoui",   "5 Rue de Fès, Tétouan",       "eau"),
    ("500789", "Fatima Benali",  "34 Bd Pasteur, Tanger",       "electricite"),
    ("500321", "Karim Tazi",     "8 Rue Ibn Batouta, Tanger",   "eau+electricite"),
    ("500654", "Salma Idrissi",  "21 Av. des FAR, Tétouan",     "eau"),
]

FACTURES = [
    ("500123", "mai 2026",  245.50, "payee"),
    ("500123", "juin 2026", 312.80, "impayee"),
    ("500456", "mai 2026",  98.20,  "payee"),
    ("500456", "juin 2026", 105.60, "impayee"),
    ("500789", "juin 2026", 187.35, "payee"),
    ("500321", "juin 2026", 421.00, "impayee"),
    ("500654", "juin 2026", 76.90,  "payee"),
]


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO clients VALUES (?, ?, ?, ?)", CLIENTS
        )
        conn.executemany(
            "INSERT INTO factures (numero_contrat, mois, montant, statut) "
            "VALUES (?, ?, ?, ?)",
            FACTURES,
        )
    print(f"Base créée : {DB_PATH}")
    print(f"  {len(CLIENTS)} clients, {len(FACTURES)} factures.")


if __name__ == "__main__":
    main()
