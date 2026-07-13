# REPRISE DU PROJET — Chatbot Amendis (à lire par Claude Code en premier)

> Passation entre deux sessions Claude Code sur deux PC différents.
> Contient TOUT le contexte : état du projet, mode de travail exigé,
> décisions prises, réinstallation et pièges déjà rencontrés.
> **Lis-le en entier avant d'agir.**
>
> **Dernière mise à jour : 13 juillet 2026** (fin de session PC n°2).
> Le gros de la transformation est FAIT et poussé sur GitHub (commit `cbdd750`).

---

## ⚠️ 1. MODE DE TRAVAIL OBLIGATOIRE : TUTEUR, PAS GÉNÉRATEUR

L'utilisatrice (Diyae, stagiaire en stage d'observation, encadrée par Mr. Otman TRIATE)
a demandé de **ne plus générer de code qu'elle ne comprend pas**. Objectif :
être capable d'expliquer chaque fichier et de réécrire le bot seule (soutenance).

**Règles :**
- Expliquer d'abord, la faire écrire ensuite, relire/corriger enfin.
- Ne JAMAIS écrire un fichier de code complet à sa place **sauf demande explicite**
  (elle en fait parfois quand elle est pressée — respecter le « accélère »).
- Vérifier la compréhension par de petites questions de reformulation.
- Avancer par petites étapes, une notion à la fois.
- Les scripts d'infrastructure (installation, commandes, lancement de services)
  peuvent être exécutés directement — c'est le **code du bot** qui passe par elle.

**Où en est son apprentissage (acquis, ne pas ré-expliquer de zéro) :**
- Boucle Rasa : message → NLU (intention+confiance) → policy → action → réponse. ✅
- `domain.yml` = inventaire (QUOI) vs `rules.yml` = câblage (QUAND). ✅
- `nlu.yml` = exemples ; le classificateur généralise. ✅
- `config.yml` : pipeline NLU (tokenizer → featurizers → DIET → FallbackClassifier)
  vs policies. ✅
- **Le mécanisme du fallback** : DIET calcule la confiance, le FallbackClassifier
  la compare au seuil et réécrit en `nlu_fallback` si trop basse → RAG. ✅
- **NOUVEAU (acquis cette session)** :
  - Le RAG de bout en bout : scraper → ingest (chunks → embeddings → ChromaDB) →
    rag_api (retrieval k + prompt strict + Ollama). ✅
  - Le câblage HTTP complet : Streamlit → Rasa (5005) → action server (5055) →
    RAG FastAPI (8000) → Ollama (11434). « Aucune magie, que du HTTP + JSON ». ✅
  - `actions.py` : Rasa n'exécute jamais le Python lui-même, il appelle l'action
    server par HTTP ; le `name()` fait la correspondance. ✅
  - Le **piège du softmax** : un classificateur répartit 100 % de sa confiance
    entre les classes connues → une question métier peut être classée « politesse »
    avec une confiance ÉLEVÉE (constaté : « comment payer ma facture » → remercier
    à 0,94). Le seuil de fallback ne protège que des confiances BASSES. Solution :
    une intention « panier » `question_documentaire`. ✅
  - Le front Streamlit et le lancement des 4 services. ✅

---

## 2. LE PROJET EN BREF

PoC de chatbot d'assistance client pour **Amendis** (eau/électricité, Tanger-Tétouan),
stage de 4 semaines. Architecture hybride :
- **Rasa 3.6** : NLU + dialogue déterministe (politesses uniquement, voir §3).
- **RAG (LangChain + ChromaDB + Ollama)** : répond à partir du contenu scrapé de
  **www.amendis.ma** (60 pages).
- **Front Streamlit** ↔ API REST Rasa (port 5005).
- Le RAG est un **service FastAPI séparé (port 8000)** appelé par l'action Rasa
  `action_rag_fallback` — séparation imposée par le conflit pydantic v1 (Rasa) /
  pydantic v2 (LangChain) : **deux venvs obligatoires**.

**Adaptation vs cahier des charges** : sources = site public www.amendis.ma (pas
des PDF). www.amendisclient.ma (espace client, SPA Angular derrière login) sert
uniquement de cible de redirection.

---

## 3. ✅ DÉCISION « 100 % DOCUMENTAIRE » — APPLIQUÉE (plus à faire)

Architecture **« Rasa minimal », SANS SQLite**, choisie et **implémentée** le 13/07/2026 :

- Rasa ne gère QUE les politesses (`saluer`, `au_revoir`, `remercier`).
- Une intention « panier » `question_documentaire` capte les questions métier et
  les route vers le RAG (via règle → `action_rag_fallback`).
- Les phrases vraiment inconnues tombent sous le seuil → `nlu_fallback` → RAG aussi.
- Le RAG répond uniquement à partir du corpus amendis.ma (zéro hallucination),
  et l'action ajoute les **URLs sources** en bas de réponse.

**Ce qui a été SUPPRIMÉ du code** (fait, committé) : dossier `database/`,
`facture_form`, entité/slot `numero_contrat`, `RegexEntityExtractor` +
`EntitySynonymMapper`, les actions SQLite, les intentions `consulter_facture` /
`payer_facture` / `signaler_fuite` / `donner_numero_contrat`.

**Seuil FallbackClassifier** monté de 0,6 → **0,75** (config.yml).

⚠️ **Écart avec le cahier des charges validé** (SQLite = livrable 1) :
**INFORMER Mr. TRIATE** de ce changement d'architecture. Toujours pas fait.

---

## 4. ÉTAT D'AVANCEMENT (au 13/07/2026)

| Étape | État |
|---|---|
| Réinstallation (Python 3.10, venv_rasa, venv_rag) | ✅ faite sur PC n°2 |
| Corpus scrapé (60 pages) | ✅ |
| Transformation documentaire (6 fichiers Rasa) | ✅ committée |
| `rasa data validate` + `rasa train` | ✅ OK |
| Vectorisation ChromaDB (`ingest.py`) | ✅ (241 fragments) |
| Ollama + `llama3.2` | ✅ installé et pull |
| **RAG testé de bout en bout** (`/ask`) | ✅ **1re fois, ça marche** |
| Chaîne complète Streamlit → Rasa → RAG → Ollama | ✅ testée, fonctionne |
| Bug NLU (softmax) trouvé et corrigé | ✅ intention panier |
| Améliorations RAG (bruit, MMR, sources) | ✅ committées |

**RESTE À FAIRE (prochaine session) :**
1. ⚠️ **Prévenir Mr. TRIATE** de l'abandon de SQLite.
2. 📄 Mettre à jour la doc `docs/documentation-projet.html` (décrit encore
   l'archi SQLite) puis régénérer le PDF (voir §8).
3. Enrichir `nlu.yml` à partir des erreurs de classification (ex. le charabia
   pur « blabla xyz » est encore classé `saluer` à 0,87 — limite connue).
4. Qualité RAG encore imparfaite sur certaines questions générales (« qui est
   Amendis », « actualités ») : le retriever remonte des pages carrières/presse
   plutôt que « qui-sommes-nous ». Pistes : re-scraper en ciblant mieux, ou
   ajuster le chunking. Piste déjà appliquée : filtrage du bruit de navigation
   + MMR k=6 dans `rag_api.py`.
5. Rapport de stage.

---

## 5. ARBORESCENCE DU REPO (versionné)

```
chatbot/
├── README.md
├── REPRISE-PROJET.md          # ce fichier
├── requirements-rasa.txt      # rasa==3.6.21, rasa-sdk==3.6.2
├── rasa_bot/
│   ├── config.yml             # pipeline NLU (DIET, fallback 0.75) + policies
│   ├── domain.yml             # 4 intents (3 politesses + question_documentaire
│   │                          #   + nlu_fallback), 3 utter, action_rag_fallback
│   ├── endpoints.yml          # action server localhost:5055
│   ├── credentials.yml        # canal REST
│   ├── data/{nlu,rules,stories}.yml
│   └── actions/actions.py     # 1 action : ActionRagFallback (appel RAG + sources)
├── rag_service/
│   ├── requirements.txt
│   ├── scraper.py             # crawler www.amendis.ma → corpus/*.txt (max 60)
│   ├── ingest.py              # corpus → chunks 800/120 → embeddings → ChromaDB
│   │                          #   (filtre le bruit de navigation)
│   └── rag_api.py             # FastAPI /ask : retrieval MMR k=6 + prompt + Ollama
├── frontend/app.py            # chat Streamlit → API REST Rasa
└── docs/                      # documentation (encore archi SQLite, À METTRE À JOUR)
```

**Absent du repo (gitignoré) — à régénérer sur le nouveau PC :**
`venv_rasa/`, `venv_rag/`, `rasa_bot/models/`, `rag_service/corpus/*.txt`,
`rag_service/chroma_db/`. (Le dossier `database/` a été supprimé, plus de SQLite.)

---

## 6. RÉINSTALLATION SUR UN NOUVEAU PC (dans cet ordre)

Prérequis : **~10 Go d'espace disque libre** (vérifier AVANT).

1. **Python 3.10 impérativement** (Rasa 3.6 refuse 3.11+) :
   `winget install --id Python.Python.3.10 --scope user --accept-package-agreements --accept-source-agreements --silent`
   → binaire : `%LOCALAPPDATA%\Programs\Python\Python310\python.exe`
2. **venv Rasa** :
   ```powershell
   & "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" -m venv venv_rasa
   venv_rasa\Scripts\python -m pip install --upgrade pip
   venv_rasa\Scripts\pip install -r requirements-rasa.txt        # ~10 min
   ```
3. **venv RAG** (`--no-cache-dir`, PyTorch volumineux) :
   ```powershell
   & "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" -m venv venv_rag
   venv_rag\Scripts\python -m pip install --upgrade pip
   venv_rag\Scripts\pip install --no-cache-dir -r rag_service\requirements.txt
   ```
4. **⚠️ Visual C++ Redistributable** (sinon PyTorch plante au chargement de
   `c10.dll`, WinError 1114 — c'était LA cause de l'échec sur le PC n°1, PAS le
   disque plein comme on croyait) :
   `winget install --id Microsoft.VCRedist.2015+.x64 --accept-package-agreements --accept-source-agreements`
5. **Corpus** : `venv_rag\Scripts\python rag_service\scraper.py` (≈ 2 min).
6. **Vectorisation** : `$env:PYTHONIOENCODING="utf-8"; venv_rag\Scripts\python rag_service\ingest.py`
   ⚠️ La variable `PYTHONIOENCODING=utf-8` est **obligatoire** sinon le script
   plante sur un `print` contenant le caractère `→` (console Windows cp1252).
7. **Ollama** : `winget install Ollama.Ollama` puis `ollama pull llama3.2` (~2 Go).
   Ollama tourne ensuite en service d'arrière-plan (port 11434, icône barre système),
   PAS besoin d'un terminal dédié. Modèle configurable via env `OLLAMA_MODEL`.
8. **Entraîner** : `cd rasa_bot ; ..\venv_rasa\Scripts\rasa train`

**LANCEMENT COMPLET — 4 terminaux (procédure vérifiée le 13/07) :**

| # | Commande (depuis…) | Port |
|---|---|---|
| 1 | `..\venv_rasa\Scripts\rasa run actions` (depuis `rasa_bot`) | 5055 |
| 2 | `..\venv_rasa\Scripts\rasa run --enable-api --cors "*"` (depuis `rasa_bot`) | 5005 |
| 3 | `$env:PYTHONIOENCODING="utf-8"; venv_rag\Scripts\python -m uvicorn rag_service.rag_api:app --port 8000` (racine) | 8000 |
| 4 | `venv_rag\Scripts\streamlit run frontend\app.py` (racine) | 8501 |

Test rapide sans front : `rasa shell` (ou `rasa shell nlu` pour la seule compréhension).

---

## 7. PIÈGES DÉJÀ RENCONTRÉS (ne pas re-perdre du temps)

| Problème | Cause / Solution |
|---|---|
| PyTorch : `OSError WinError 1114 ... c10.dll` à l'import (via ingest) | **Manque Visual C++ Redistributable**. Installer `Microsoft.VCRedist.2015+.x64`. C'était la vraie cause de l'échec du PC n°1. |
| `ingest.py` : `UnicodeEncodeError '→'` (charmap) | Console Windows cp1252 ne gère pas `→`. Lancer avec `$env:PYTHONIOENCODING="utf-8"`. |
| `Remove-Item chroma_db` : « file used by another process » | Le service RAG (uvicorn) verrouille la base. **Éteindre uvicorn AVANT** de re-vectoriser, sinon les fragments s'ajoutent en double. |
| `cd C:\Users\Diyae Ziyani\...` échoue | Espace dans le chemin → mettre le chemin **entre guillemets**. |
| `cd rasa_bot` échoue « PathNotFound » | On est déjà DANS `rasa_bot`. |
| NLU : question métier classée « politesse » à confiance élevée | Piège du softmax. Résolu par l'intention panier `question_documentaire` (§3). |
| `pip install` « No space left on device » | Disque plein. Vérifier l'espace AVANT. |
| Scraper : `UnicodeEncodeError latin-1` | En-têtes HTTP doivent être ASCII (User-Agent sans tiret long). Déjà corrigé. |
| Rasa : télémétrie `charmap codec` au 1er lancement | Bénin, la télémétrie se désactive seule. |
| Warnings SQLAlchemy/pkg_resources/matplotlib/jax au lancement | Bruit normal de Rasa 3.6, ignorer. |
| Rasa lent à démarrer / 1re époque longue | Normal sur CPU (TensorFlow). Patience (~1-2 min). |

---

## 8. DIVERS

- Langue de travail : **français** (code commenté en français aussi).
- OS : Windows 11 ; shell PowerShell 5.1 (pas de `&&`, chemins avec espaces
  entre guillemets).
- Git : identité configurée localement (Diyae Ziyani / ziyanidiyae0@gmail.com).
  Remote : https://github.com/diyaeziyani10/chatbot.git — pousser sur `main`.
- Le PDF `docs/Documentation-Chatbot-Amendis.pdf` se régénère depuis
  `docs/documentation-projet.html` via Edge headless :
  `msedge --headless --no-pdf-header-footer --print-to-pdf="docs\Documentation-Chatbot-Amendis.pdf" "file:///<chemin>/docs/documentation-projet.html"`
- Jalons : NLU validé mi-juillet 2026, RAG fin juillet, livraison fin de stage.
