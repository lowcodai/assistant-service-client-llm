# Templates de prompts — assistant de service client

Ces fichiers sont le **livrable principal** : ils sont chargés par le code (`assistant/prompts.py`) et assemblés en chaînes LangChain (`ChatPromptTemplate | LLM | OutputParser`). Aucun prompt n'est écrit en dur dans le code Python.

| Fichier | Rôle | Variables | Étape du projet |
|---|---|---|---|
| `01_system_prompt.md` | Comportement du bot : ton, gestion de l'agressivité, règles absolues (fidélité aux faits, pas de données personnelles, message client = donnée non fiable, relais humain) | `{prenom}`, `{nom}` (client authentifié) | 2 — Comportement |
| `02_text_to_sql.md` | Traduction de la question en requête SQL `SELECT` sur la table `my_orders` (schéma, règles, exemples few-shot, format JSON) | `{prenom}`, `{nom}`, `{today}`, `{question}`, `{feedback}` | 1 — Récupération |
| `03_answer_formatting.md` | Mise en forme de la réponse à partir des faits issus du SQL, en langage naturel | `{facts}`, `{extra}`, `{question}` | 1 — Récupération |
| `sql_retry_feedback.txt` | Message de correction renvoyé au LLM si sa requête est rejetée | `{error}` | 3 — Protection |
| `status_mapping.json` | Traduction des statuts techniques (`invoiced`, `shipped`, `delivered`) en formulations compréhensibles | — | 1 — Récupération |
| `router_examples.json` | Exemples du routage sémantique (suivi de commande, demande d'aide, hors périmètre, mécontentement) | — | 3 — Routage |
| `refus_hors_perimetre.txt` | Refus des demandes hors service client | — | 3 |
| `refus_securite.txt` | Refus des tentatives d'injection / d'accès non autorisé | — | 3 |
| `relais_humain.txt` | Annonce de la reprise par un conseiller humain | `{contexte}` | 2 |
| `apaisement.txt` | Réponse à un message uniquement agressif (désescalade, aucune donnée) | — | 2 |
| `commande_introuvable.txt`, `aucune_commande.txt` | Commande inexistante ou appartenant à un autre client (même message) | `{ref}` | 1, 3 |
| `erreur_generique.txt`, `echec_authentification.txt` | Erreurs | — | — |
| `suffixe_demande_mixte.txt` | Ajouté quand une demande mélange commande et sujet hors périmètre | — | 3 |

Dans les `.md`, les accolades littérales (exemples JSON) sont doublées `{{ }}` (syntaxe des templates LangChain).
