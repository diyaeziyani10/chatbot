# Les changements « intelligence » — explication détaillée


---

## Vue d'ensemble : les 7 problèmes corrigés

| # | Problème constaté (test réel) | Solution | Fichier |
|---|---|---|---|
| 1 | « abonnement Maroc Telecom » → « pas trouvé dans la doc » (il a CHERCHÉ au lieu de comprendre) | Règle « hors-domaine » : refus + rebond | `rag_api.py` (prompt) |
| 2 | « qui es-tu ? » → récitation de la page « à propos d'Amendis » | Persona : le bot se connaît | `rag_api.py` (prompt) |
| 3 | Aucune mémoire (« et pour l'électricité ? » incompris ; rien retenu d'un jour à l'autre) | Mémoire persistante par utilisateur | `rag_api.py`, `actions.py`, `frontend/app.py` |
| 4 | Réponses passives, sans suite | Proactivité : suggestion contextuelle en fin de réponse | `rag_api.py` (prompt) |
| 5 | « oui » (réponse à une suggestion) → « Bonjour ! » | Affirmations dans le NLU + reformulation de question | `nlu.yml`, `rag_api.py` |
| 6 | « offres de travail d'Amendis » → refus… suivi de la réponse (contradiction) | Domaine élargi + interprétation d'intention | `rag_api.py` (prompt) |
| 7 | Quota Groq épuisé (100 000 tokens/jour) → panne | Chaîne de secours LLM à 3 niveaux | `rag_api.py` |

---

## 1. Le prompt « persona » (rag_service/rag_api.py)

**Avant** : le prompt disait seulement « réponds à partir des extraits, sinon
dis que tu n'as pas trouvé ». Résultat : face à « Maroc Telecom » ou
« qui es-tu ? », le bot ne savait faire qu'une chose — chercher dans les
extraits — d'où des réponses de moteur de recherche.

**Après** : le prompt est devenu un véritable **contrat de comportement**,
structuré en sections :

- **TON IDENTITÉ** : qui est le bot (assistant IA d'Amendis), ce qu'il sait
  faire, ses limites. Quand on l'interroge sur lui-même, il répond depuis
  cette section — pas depuis les extraits.
- **TON DOMAINE** : *tout ce qui concerne Amendis* — les services clients
  (factures, abonnements, fuites...) ET l'entreprise elle-même (carrières,
  stages, actualités, engagements). Suivi de la consigne d'**interprétation
  d'intention** : « demande-toi ce que l'utilisateur cherche réellement ;
  en cas de doute, considère que ça concerne Amendis et cherche — ne refuse
  jamais par excès de prudence ». (Correction du bug n°6 : le domaine était
  défini trop étroitement comme « services d'eau et d'électricité », donc les
  questions carrières étaient refusées… puis répondues quand même.)
- **7 CAS DE RÉPONSE** numérotés : question métier → extraits ; question sur
  soi → identité ; hors-domaine → refus SANS donner d'information (« ne le
  définis pas, ne l'explique pas — même si tu connais la réponse ») + rebond
  vers le service Amendis analogue ; info absente → aveu honnête ; suivi →
  historique ; ambiguïté → question de clarification ; et **proactivité** →
  une suggestion pertinente en fin de réponse, déduite de la situation
  (abonnement d'eau → proposer l'électricité ; paiement → proposer l'espace
  client...), jamais inventée, jamais après un refus.

**Concept à retenir** : avec un LLM, tout ce qui n'est pas explicitement
spécifié sera improvisé. Le comportement d'un assistant se conçoit comme un
contrat écrit — c'est le métier de *prompt engineering*. Chaque remarque de
l'encadrant s'est traduite par une règle précise du contrat.

## 2. La mémoire persistante par utilisateur

**Le besoin** : « si un utilisateur demande les pièces pour un abonnement
hier, et redemande aujourd'hui, le bot doit se rappeler ».

**Les 3 briques** :

1. **Une identité stable** (`frontend/app.py`) : champ « 🪪 votre nom ou n°
   de client » sous le chat. S'il est rempli, ce nom devient le `sender_id`
   envoyé à Rasa (sinon : UUID aléatoire = utilisateur anonyme, mémoire
   limitée à la session). Fonction `sender_id()`.
2. **La transmission** (`rasa_bot/actions/actions.py`) : l'action envoie
   maintenant `{"question": ..., "user_id": tracker.sender_id}` au service
   RAG — le `sender_id` traverse toute la chaîne Streamlit → Rasa → action.
3. **Le stockage et la relecture** (`rag_service/rag_api.py`) : un fichier
   JSON par utilisateur dans `rag_service/memoire/` (identifiant assaini par
   regex pour éviter toute injection de chemin ; 50 échanges conservés max).
   À chaque question, les 6 derniers échanges (avec leurs dates) sont
   injectés dans le prompt : le LLM peut comprendre les questions de suivi
   et rappeler les échanges passés, même d'un autre jour.

**Vie privée** : la mémoire est exclue de Git (`.gitignore`), stockée
uniquement en local, jamais indexée dans ChromaDB. En production, il
faudrait un consentement explicite et une durée de rétention (RGPD/loi 09-08).

## 3. La reformulation de question (« condense question »)

**Le bug** : après une suggestion du bot, l'utilisateur répond « oui je veux
savoir les deux » → deux problèmes en cascade :
1. Rasa classait « oui » comme… une salutation (`saluer` à 0,94) → « Bonjour ! ».
   Le NLU n'avait jamais vu d'affirmations. **Correction** : 12 exemples
   (« oui », « d'accord », « je veux les deux »...) ajoutés à l'intention
   `question_documentaire` dans `nlu.yml` + réentraînement. Vérifié :
   « oui » → `question_documentaire` à 100 %.
2. Même arrivé au RAG, « oui » ne peut rien trouver par similarité vectorielle
   (aucun sens propre). **Correction** : nouvelle étape `question_autonome()`
   dans `rag_api.py` — quand un historique existe, un premier appel LLM
   reformule le message en question complète (« oui » → « comment consulter
   ma facture en ligne et quels sont les moyens de paiement ? ») et c'est
   ELLE qui interroge ChromaDB. La question originale + l'historique servent
   ensuite à rédiger la réponse.

**Concept** : c'est le pattern RAG standard dit *condense question* — le pont
entre la mémoire conversationnelle et la recherche vectorielle. Coût :
un appel LLM léger en plus (~0,5 s) quand il y a un historique.

## 4. La chaîne de secours LLM (résilience)

**L'incident** : en pleine séance de tests, erreur 429 de Groq — le quota
gratuit du modèle 70b est de **100 000 tokens/jour**, soit ~20-30 questions
(chaque question consomme ~3-6 000 tokens : prompt + 6 extraits + historique
+ reformulation).

**La solution** (`rag_api.py`) : une liste `LLMS` essayée dans l'ordre à
chaque requête par la fonction `generer()` :
1. `groq/llama-3.3-70b-versatile` — qualité maximale ;
2. `groq/llama-3.1-8b-instant` — quota séparé bien plus large, qualité correcte ;
3. `ollama/llama3.2` — local, lent, mais fonctionne sans internet.

Si un niveau échoue (quota, réseau, service éteint), le suivant prend le
relais silencieusement : **le bot ne tombe jamais en panne**. Testé en
conditions réelles (quota 70b réellement épuisé → réponses servies par le 8b,
qualité toujours bonne). La reformulation (tâche simple) est confiée
d'office au 8b pour économiser le quota du 70b.

**Conseil démo** : ne pas faire de grosse séance de tests juste avant la
présentation (garder le quota 70b) ; vérifier le modèle actif sur
http://localhost:8000/health.

## 5. Fichiers annexes

- **TESTS.md** (nouveau) : plan de test manuel complet — 12 sections avec les
  phrases exactes à taper et les comportements attendus, y compris les tests
  de l'encadrant (Maroc Telecom, « qui es-tu »), la mémoire inter-sessions
  et les tests de panne.
- **.gitignore** : + `rag_service/memoire/` (données personnelles).

---

## Après modification, quel service redémarrer ?

| Fichier modifié | À redémarrer |
|---|---|
| `rag_service/rag_api.py` | T2 (uvicorn) |
| `rasa_bot/actions/actions.py` | T1 (rasa run actions) |
| `frontend/app.py` | T4 (streamlit) |
| `nlu.yml` / `domain.yml` / `rules.yml` / `config.yml` | `rasa train` PUIS T3 (rasa run) |

## Argumentaire soutenance : « où est l'intelligence ? »

1. **Compréhension** : NLU neuronal (DIET) tolérant aux fautes + recherche
   par le SENS (embeddings 384 dimensions), pas par mots-clés.
2. **Discernement** : distingue question métier / question sur lui-même /
   hors-domaine / information manquante — et réagit différemment à chacune.
3. **Mémoire** : suit la conversation (« et pour l'électricité ? ») et se
   souvient des utilisateurs d'un jour à l'autre.
4. **Initiative** : questions de clarification quand c'est flou, suggestions
   proactives adaptées à la situation.
5. **Honnêteté** : ne répond jamais hors de sa documentation, cite ses
   sources, avoue quand il ne sait pas — zéro hallucination par conception.
6. **Résilience** : bascule automatique entre 3 moteurs LLM selon la
   disponibilité.
