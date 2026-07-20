# Plan de test manuel — Chatbot Amendis

À dérouler dans l'ordre, dans Streamlit, avant chaque démonstration.
Pour chaque test : la phrase exacte à taper, le comportement attendu, et
quoi vérifier. Cocher ✅/❌ et noter les réponses bizarres pour amélioration.

## 0. Préparation

1. Lancer les 4 terminaux (voir README) et attendre que chacun soit prêt :
   - T1 : `Action endpoint is up and running`
   - T2 : `Uvicorn running on http://127.0.0.1:8000` (~30 s de chargement)
   - T3 : `Rasa server is up and running`
   - T4 : le navigateur s'ouvre sur http://localhost:8501
2. Vérifier http://localhost:8000/health → doit afficher
   `"model": "groq/llama-3.3-70b-versatile"` (= le cloud est actif ;
   si `ollama/...`, la clé .env n'est pas chargée → réponses très lentes).
3. ⚠️ Après toute modification de `rag_api.py` → redémarrer T2 ;
   `actions.py` → T1 ; `frontend/app.py` → T4 ; fichiers yml → `rasa train` + T3.

## 1. Politesses (Rasa seul — doit être INSTANTANÉ, < 1 s)

| Taper | Attendu |
|---|---|
| `bonjour` | Message d'accueil, instantané (le LLM n'est pas appelé) |
| `merci beaucoup` | « Je vous en prie... », instantané |
| `au revoir` | Message d'au revoir, instantané |
| `bnojour` (faute volontaire) | Quand même reconnu comme salutation |

**Si lent (~8 s)** : la question est partie au RAG → le NLU n'a pas reconnu
la politesse (vérifier `nlu.yml`).

## 2. Questions métier (RAG — ~8 s, avec liens sources 🔗)

| Taper | Vérifier |
|---|---|
| `comment payer ma facture ?` | Étapes concrètes (#655#, GAB...), liens 🔗 vers amendis.ma |
| `quels documents pour un abonnement ?` | Liste par cas (locataire/propriétaire...), question de clarification à la fin |
| `comment résilier mon contrat ?` | Démarche cohérente avec la FAQ du site |
| `comment est calculée ma consommation d'eau ?` | Réponse tirée de la FAQ |

**Vérifier à chaque fois** : les liens 🔗 pointent vers des pages amendis.ma
pertinentes et s'ouvrent au clic ; aucun chiffre/tarif inventé (comparer au
site en cas de doute).

## 3. Zéro hallucination (info absente du corpus)

| Taper | Attendu |
|---|---|
| `quel est le prix exact du kWh en 2026 ?` | « Je n'ai pas trouvé cette information... 05 39 32 88 88 » — PAS de chiffre inventé |
| `quel est le salaire du directeur d'Amendis ?` | Refus honnête, pas d'invention |

## 4. Hors-domaine (les tests de l'encadrant !)

| Taper | Attendu |
|---|---|
| `donne-moi les documents pour un abonnement à Maroc Telecom` | Refus poli SANS chercher + rebond « En revanche... abonnement Amendis » |
| `qui est netflix` | Refus SANS expliquer ce qu'est Netflix |
| `c'est quoi la capitale du Japon ?` | Refus, ne donne PAS la réponse |
| `comment fonctionne l'abonnement Orange ?` | Refus sur Orange, propose l'abonnement Amendis |

**⚠️ Point de vigilance** : vérifier qu'aucun lien 🔗 non pertinent ne
s'affiche sous les refus hors-domaine (les liens sont ajoutés par actions.py ;
si des liens parasites apparaissent sous un refus, le signaler → petit
ajustement à faire dans actions.py).

## 5. Identité du bot (l'autre test de l'encadrant)

| Taper | Attendu |
|---|---|
| `qui es-tu ?` | Se présente comme assistant IA d'Amendis + liste ses capacités + propose son aide (PAS une récitation de la page « à propos ») |
| `que sais-tu faire ?` | Liste claire de ses capacités |
| `comment tu fonctionnes ?` | Explication simple (IA, documentation officielle, sources) |

## 6. Clarification (question vague)

| Taper | Attendu |
|---|---|
| `j'ai un problème` | UNE question de clarification (« s'agit-il de... ? »), pas une réponse au hasard |
| `ma facture` | Demande de précision |

## 7. Proactivité (suggestions)

| Taper | Suggestion attendue en fin de réponse |
|---|---|
| `je veux un abonnement d'eau` | « Souhaitez-vous aussi un abonnement d'électricité ? » |
| `comment payer ma facture ?` | Espace client / historique / autre moyen de paiement |
| `il y a une fuite d'eau devant chez moi` | Numéro d'urgence ou aide supplémentaire |

Et vérifier l'inverse : PAS de suggestion après un refus hors-domaine.

## 8. Mémoire courte (suivi de conversation)

Enchaîner dans la même session (remplir d'abord le champ 🪪 avec un nom) :
1. `quels documents pour un abonnement d'eau ?` → réponse
2. `et pour l'électricité ?` → doit comprendre qu'on parle TOUJOURS des
   documents d'abonnement (pas répondre sur autre chose)
3. `peux-tu me rappeler ma première question ?` → doit la citer

## 9. Mémoire persistante (le test « hier / aujourd'hui » de l'encadrant)

1. Remplir le champ 🪪 avec un nom (ex : `diyae`), poser :
   `quels documents pour un abonnement ?`
2. **Fermer l'onglet** (ou Ctrl+C sur T4 puis relancer Streamlit)
3. Rouvrir, **remettre le même nom** dans 🪪, taper :
   `te souviens-tu de ce que je t'ai demandé ?`
4. ✅ Attendu : il rappelle la question sur les documents d'abonnement.
5. Contre-test : refaire avec un AUTRE nom → il ne doit rien « se rappeler ».

## 10. Interface

- [ ] La question apparaît IMMÉDIATEMENT, puis « ... » animé, puis la réponse
- [ ] Le chat défile DANS sa boîte (la page ne s'allonge pas), collé en bas
- [ ] Pas de mention « Press Enter to submit form » sous le champ
- [ ] Les 4 chips de sujets fréquents fonctionnent au clic
- [ ] Logos corrects : Amendis à gauche, « opéré par Veolia » à droite
- [ ] Les liens 🔗 dans les réponses sont cliquables (nouvel onglet)

## 11. Robustesse (pannes)

1. **Arrêter T2** (Ctrl+C sur uvicorn), poser une question métier →
   attendu : « Le service de documentation est momentanément indisponible »
   (message propre, pas de crash). Relancer T2.
2. **Arrêter T1** (action server), question métier → Streamlit affiche un
   message d'erreur propre. Relancer T1.
3. Envoyer un message vide / seulement des espaces → rien ne se casse.
4. Message très long (copier un paragraphe entier) → réponse normale.

## 12. Performance (chronométrer 3 questions métier)

- Attendu : ~6-10 s par question documentaire, politesses < 1 s.
- Si > 30 s : vérifier /health (Groq actif ?) et la connexion internet.

---

**Après les tests** : noter chaque ❌ avec la phrase exacte tapée et la
réponse obtenue — ce sont les données pour améliorer le prompt ou `nlu.yml`.
