# REPRISE DU PROJET — Chatbot Amendis (à lire par Claude Code en premier)

> Ce fichier est une passation entre deux sessions Claude Code sur deux PC différents.
> Il contient TOUT le contexte : état du projet, mode de travail exigé par l'utilisatrice,
> décisions prises, étapes de réinstallation et pièges déjà rencontrés.
> **Lis-le en entier avant d'agir.**

---

## ⚠️ 1. MODE DE TRAVAIL OBLIGATOIRE : TUTEUR, PAS GÉNÉRATEUR

L'utilisatrice (Diyae, stagiaire en stage d'observation, encadrée par Mr. Otman TRIATE)
a explicitement demandé de **ne plus générer de code qu'elle ne comprend pas**.
Son objectif : être capable d'expliquer chaque fichier et de réécrire le bot seule
(elle devra le défendre en soutenance).

**Règles à respecter :**
- Expliquer d'abord, faire écrire l'utilisatrice ensuite, relire/corriger enfin.
- Ne JAMAIS écrire un fichier de code complet à sa place sauf demande explicite.
- Vérifier la compréhension en lui demandant de reformuler ou via de petites questions.
- Avancer par petites étapes ; une notion à la fois.
- Les scripts d'infrastructure (installation, commandes) peuvent être exécutés
  directement — c'est le code du bot qui doit passer par elle.

**Où en est son apprentissage (déjà acquis, ne pas re-expliquer de zéro) :**
- Le modèle mental de la boucle Rasa : message → NLU (intention+entités) →
  policy (choix d'action) → action → réponse. ✅
- `domain.yml` = inventaire (le QUOI) vs `rules.yml` = câblage (le QUAND). ✅
- `nlu.yml` = exemples d'entraînement ; le classificateur généralise, ne mémorise pas. ✅
- A testé `rasa shell nlu` elle-même : a vu intention/confidence/intent_ranking,
  et a constaté qu'une confiance élevée ≠ réponse correcte (piège du mot « dois »
  qui a fait classer « je voudrais régler ce que je dois » en consulter_facture). ✅
- `config.yml` : pipeline = chaîne de montage NLU (tokenizer → featurizers → DIET →
  FallbackClassifier seuil 0,6) ; policies = décision. Expliqué, à consolider. ✅
- **Pas encore vu en pratique** : actions.py, le RAG de bout en bout, stories/TED,
  le front Streamlit.

**Prochaine étape pédagogique convenue** : transformer le projet en architecture
« 100 % documentaire » (voir §3), C'EST ELLE QUI TIENT LE CLAVIER, Claude guide.

---

## 2. LE PROJET EN BREF

PoC de chatbot d'assistance client pour **Amendis** (eau/électricité, Tanger-Tétouan),
stage de 4 semaines (cahier des charges : `Cahier des charges- Chatbot.pdf`, fourni
par l'utilisatrice au besoin). Architecture hybride :
- **Rasa 3.6** : NLU + dialogue déterministe pour les demandes fréquentes.
- **RAG (LangChain + ChromaDB + Ollama)** : fallback documentaire quand la confiance
  NLU < 0,6 — répond uniquement à partir du contenu scrapé de **www.amendis.ma**.
- **Front Streamlit** ↔ API REST Rasa (port 5005).
- Le RAG est un **service FastAPI séparé (port 8000)** appelé par l'action Rasa
  `action_rag_fallback` — séparation imposée par le conflit pydantic v1 (Rasa) /
  pydantic v2 (LangChain) : **deux venvs obligatoires**.

**Adaptation vs cahier des charges** : les sources documentaires ne sont pas des PDF
mais le site public www.amendis.ma (60 pages scrapées). Le site www.amendisclient.ma
(espace client) est une SPA Angular derrière login → non scrapable, sert uniquement
de cible de redirection (« payez sur votre espace client »).

---

## 3. ⚠️ DÉCISION RÉCENTE NON ENCORE APPLIQUÉE AU CODE

L'utilisatrice a choisi (question posée, réponse explicite) : **architecture
« 100 % documentaire », SANS SQLite**.

- Toutes les intentions deviennent documentaires : réponse contrôlée + lien vers la
  bonne page amendis.ma ; le RAG reste le filet de sécurité pour tout le reste.
- Pour « ma facture », le bot explique la démarche + redirige vers amendisclient.ma
  (jamais de montant réel).
- **À supprimer du code** (le code actuel dans le repo contient encore tout ça) :
  dossier `database/`, `facture_form`, entité/slot `numero_contrat`,
  `RegexEntityExtractor` + `EntitySynonymMapper` dans config.yml,
  les actions SQLite dans actions.py, l'intention `donner_numero_contrat`.
- ⚠️ Écart avec le cahier des charges validé (SQLite = livrable 1) : il lui a été
  conseillé d'en informer son encadrant. Le lui rappeler si pertinent.
- Cette transformation est **l'exercice pratique prévu** : la guider, ne pas la faire
  à sa place.

---

## 4. ARBORESCENCE DU REPO (ce qui est versionné)

```
chatbot/
├── README.md                  # architecture + commandes (à jour, à relire)
├── REPRISE-PROJET.md          # ce fichier
├── requirements-rasa.txt      # rasa==3.6.21, rasa-sdk==3.6.2
├── rasa_bot/
│   ├── config.yml             # pipeline NLU (DIET, fallback 0.6) + policies
│   ├── domain.yml             # 8 intentions, slot numero_contrat, facture_form…
│   ├── endpoints.yml          # action server localhost:5055
│   ├── credentials.yml        # canal REST
│   ├── data/{nlu,rules,stories}.yml
│   └── actions/actions.py     # 4 actions (SQLite + appel RAG http://localhost:8000/ask)
├── database/init_db.py        # crée amendis.db (5 clients, 7 factures fictifs)
├── rag_service/
│   ├── requirements.txt
│   ├── scraper.py             # crawler www.amendis.ma → corpus/*.txt (max 60 pages)
│   ├── ingest.py              # corpus → chunks 800/120 → embeddings → ChromaDB
│   └── rag_api.py             # FastAPI /ask : retrieval k=4 + prompt strict + Ollama
├── frontend/app.py            # chat Streamlit → API REST Rasa
└── docs/                      # documentation-projet.html + PDF généré
```

**Absent du repo (gitignoré) — à régénérer sur le nouveau PC :**
`venv_rasa/`, `venv_rag/`, `rasa_bot/models/`, `rag_service/corpus/*.txt`,
`rag_service/chroma_db/`, `database/amendis.db`.

---

## 5. RÉINSTALLATION SUR LE NOUVEAU PC (dans cet ordre)

Prérequis : **~10 Go d'espace disque libre** (vérifier AVANT : le disque plein a déjà
fait échouer les installations une fois sur l'ancien PC).

1. **Python 3.10 impérativement** (Rasa 3.6 refuse 3.11+) :
   `winget install --id Python.Python.3.10 --scope user --accept-package-agreements --accept-source-agreements --silent`
   → binaire : `%LOCALAPPDATA%\Programs\Python\Python310\python.exe`
2. **venv Rasa** :
   ```powershell
   & "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" -m venv venv_rasa
   venv_rasa\Scripts\python -m pip install --upgrade pip
   venv_rasa\Scripts\pip install -r requirements-rasa.txt        # ~10 min
   ```
3. **venv RAG** (utiliser `--no-cache-dir`, PyTorch est volumineux) :
   ```powershell
   & "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" -m venv venv_rag
   venv_rag\Scripts\python -m pip install --upgrade pip
   venv_rag\Scripts\pip install --no-cache-dir -r rag_service\requirements.txt
   ```
4. **Corpus** : `venv_rag\Scripts\python rag_service\scraper.py`
   (≈ 2 min, 60 pages, 2 erreurs 403 normales sur les pages contact/newsletter)
5. **Vectorisation** : `venv_rag\Scripts\python rag_service\ingest.py`
   (télécharge le modèle d'embeddings ~470 Mo au 1er lancement)
   ⚠️ Cette étape a ÉCHOUÉ sur l'ancien PC (cause non diagnostiquée — probablement
   le disque plein ou une coupure pendant le téléchargement du modèle). Si échec :
   lire le traceback, vérifier espace disque et réseau, relancer.
6. **Ollama** (jamais installé jusqu'ici) : télécharger depuis https://ollama.com
   ou `winget install Ollama.Ollama`, puis `ollama pull llama3.2` (~2 Go).
   Le modèle est configurable via la variable d'env `OLLAMA_MODEL` (défaut llama3.2).
7. **Entraîner** : `cd rasa_bot ; ..\venv_rasa\Scripts\rasa train`
   (⚠️ NE PAS entraîner avec l'ancien domaine si la transformation documentaire (§3)
   est faite d'abord — voir « prochaines étapes »)
8. La base SQLite (`database/init_db.py`) : **ne pas la recréer** si la décision §3
   est maintenue — le dossier database/ est destiné à être supprimé.

**Lancement complet (4 terminaux)** — voir README.md. Test rapide sans front :
`rasa shell` (ou `rasa shell nlu` pour tester seulement la compréhension).

---

## 6. PIÈGES DÉJÀ RENCONTRÉS (ne pas re-perdre du temps dessus)

| Problème | Cause / Solution |
|---|---|
| `pip install` échoue « No space left on device » | Disque plein. Vérifier l'espace AVANT. |
| Scraper : `UnicodeEncodeError latin-1` | Les en-têtes HTTP doivent être ASCII. Déjà corrigé (User-Agent sans tiret long) — ne pas réintroduire de caractères non-ASCII dans HEADERS. |
| Rasa : erreur télémétrie `charmap codec` au 1er lancement | Bénin (console Windows cp1252). Ignorer, la télémétrie se désactive seule. |
| Avertissements SQLAlchemy/pkg_resources/matplotlib au lancement de rasa | Bruit normal de Rasa 3.6, ignorer. |
| Warning « overlap RegexEntityExtractor / DIETClassifier » au train | Connu ; disparaîtra avec la suppression des entités (§3). |
| Warning « utter_hors_sujet / utter_ask_numero_contrat is not used » | Faux positif (usage dynamique) ; disparaîtra aussi avec §3. |
| Rasa très lent à démarrer / 1re époque du train très longue | Normal sur CPU (TensorFlow). Patience. |

---

## 7. PROCHAINES ÉTAPES (dans l'ordre convenu avec l'utilisatrice)

1. **Réinstallation** (§5, étapes 1-3 minimum pour pouvoir travailler).
2. **Transformation « 100 % documentaire »** (§3) — EN MODE TUTEUR : elle édite
   domain.yml → nlu.yml → rules.yml → config.yml → actions.py, Claude explique
   et relit. Définir ensemble les nouvelles intentions documentaires (ex :
   payer_facture, s_abonner/brancher, comprendre_facture_conso, signaler_fuite,
   contact_agences) avec réponse + lien amendis.ma pour chacune.
3. Re-scraper + vectoriser + réentraîner, puis **tester le RAG de bout en bout**
   (uvicorn + curl sur /ask) — première fois que ce sera testé.
4. Installer Ollama, brancher le tout, test complet via `rasa shell` puis Streamlit.
5. Enrichir nlu.yml à partir des erreurs de classification constatées en test.
6. Rapport de stage (un PDF de documentation existe déjà dans docs/ — le mettre à
   jour après la transformation, il décrit encore l'architecture avec SQLite).

---

## 8. DIVERS

- Langue de travail : **français** (code commenté en français aussi).
- OS des deux PC : Windows 11 ; shell PowerShell 5.1 (pas de `&&`).
- Le PDF `docs/Documentation-Chatbot-Amendis.pdf` se régénère depuis
  `docs/documentation-projet.html` via Edge headless :
  `msedge --headless --no-pdf-header-footer --print-to-pdf="docs\Documentation-Chatbot-Amendis.pdf" "file:///<chemin>/docs/documentation-projet.html"`
- Jalons du stage : NLU validé mi-juillet 2026, RAG fin juillet, livraison fin de stage.
