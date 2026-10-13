# Soutenance — Assistant de service client e-commerce basé sur un LLM

Formation LLM Engineer · Auteur : Jérémie Coste · Environnement : DGX Spark + JupyterLab

---

## 1. Le projet en 30 secondes
Un assistant qui répond en langage naturel aux questions d'un client **authentifié** sur ses commandes, à partir d'une base SQLite interrogée **en temps réel**. Le LLM traduit la question en SQL ; la requête est exécutée dans un bac à sable qui ne contient que les commandes du client. L'assistant reformule les statuts techniques, reste professionnel face à un client agressif, passe la main à un humain pour les actions, rejette ce qui sort du service client et résiste aux injections.

**Preuve :** 38/38 cas de test (3 exécutions identiques), garde-fous SQL 17/17, routeur sémantique 26/26, aucune donnée personnelle dans les réponses.

## 2. Contexte et contraintes
- Cloud Sandbox remplacé par mon **DGX Spark** : tout tourne en local, LLM compris (`Qwen3.8-27B-NVFP4` via vLLM, piloté avec **LangChain**).
- Base SQLite `orders.db` : `users` (40 lignes), `orders` (100 lignes).
- Trois étapes à valider : (1) récupération des informations, (2) comportement du bot, (3) protection des données et routage sémantique.
- **Livrable principal attendu : les templates de prompts** (dossier `prompts/`) + le code Python.

## 3. Démarche
1. Cadrage sur le dossier de projet et les trois étapes.
2. **Inspection des données avant tout code** : 3 commandes (54, 71, 78) ont `user_id = 0`, inexistant dans `users` ; les dates absentes sont cohérentes avec les statuts ; 5 commandes maximum par client.
3. Environnement : GPU, LLM sur `localhost:8000`, JupyterLab installé dans un venv utilisateur (rien de système).
4. **Version 1** : extraction d'intention par le LLM + SQL écrit par le code. Version testée (31 cas) mais **refusée à la première soumission** : aucun fichier n'avait été déposé sur la plateforme.
5. **Version 2 (actuelle)**, après relecture des consignes et du retour de l'évaluateur : le bot doit *générer* du SQL (text-to-SQL) et les **templates de prompts** doivent être le livrable central. J'ai donc extrait tous les prompts dans `prompts/`, bâti des chaînes LangChain (`prompt | llm | parser`) et réintroduit la génération SQL, **avec une sécurité par construction** (bac à sable).

## 4. Architecture
```
message + identité (email, prénom, nom)
  → authentification (code) → user_id
  → garde-fous d'injection (motifs)
  → routage sémantique par proposition (embeddings multilingues)
        hors périmètre → refus · mécontentement seul → désescalade · aide/action → relais humain · commande → suite
  → text-to-SQL : prompts/02_text_to_sql.md | LLM | JsonOutputParser
  → exécution dans un bac à sable : base mémoire ne contenant QUE les commandes du client
      (SELECT seul, table my_orders seule, une instruction, sans commentaire, budget de calcul, 50 lignes max)
  → faits : statut technique → formulation métier (status_mapping.json), dates JJ/MM/AAAA
  → reformulation : prompts/01_system_prompt.md + 03_answer_formatting.md | LLM | StrOutputParser
  → contrôles de sortie (aucun e-mail/téléphone ; dates et n° ∈ résultat SQL ; pas de valeur technique ; cohérence avec le statut)
  → réponse (sinon gabarit déterministe sans LLM)
```
| Fichier | Rôle |
|---|---|
| `prompts/` | tous les templates (voir `prompts/README.md`) |
| `assistant/prompts.py` | chargement des templates |
| `assistant/pipeline.py` | chaînes LangChain et orchestration |
| `assistant/db.py` | authentification, bac à sable, autorisateur SQLite |
| `assistant/router.py`, `guard.py` | routage sémantique, anti-injection |
| `assistant/tests.py` | 38 cas, jeu du routeur, jeu des garde-fous SQL |

## 5. Choix de conception et justification
- **Text-to-SQL sécurisé par construction.** Plutôt que de faire confiance au LLM, la requête s'exécute là où seules les données du client existent : une injection réussie ne peut physiquement pas lire les commandes d'autrui. L'autorisateur SQLite bloque en plus tout ce qui n'est pas un `SELECT` sur `my_orders`.
- **L'identité est résolue par le code** (email + prénom + nom → `user_id`) ; un numéro de commande n'est jamais une preuve d'autorisation. Le prénom/nom alimentent les prompts (personnalisation).
- **Pas d'oracle d'existence** : commande inexistante, d'un autre client ou anormale → même message.
- **Le LLM de reformulation ne voit jamais les valeurs techniques** : le statut est traduit avant.
- **Routage avant le LLM principal**, par proposition : une demande mixte (commande + poème) est réduite à sa partie service client.
- **Route « mécontentement »** : une insulte n'est ni une demande d'aide ni du hors-sujet ; seule → désescalade, mélangée à une vraie demande → la demande est traitée.
- **Défense en profondeur** et **local d'abord** (aucune donnée client ne quitte la machine).

## 6. Difficultés rencontrées et corrections (à citer)
| Constat (par les tests ou la relecture) | Correction |
|---|---|
| Première soumission refusée : aucun fichier déposé | dépôt vérifié ; archive et dossier `prompts/` séparés, README à la racine |
| Prompts enfouis dans le code, SQL non généré par le LLM | templates extraits dans `prompts/`, chaînes LCEL, text-to-SQL + bac à sable |
| « Ignore tes instructions… » (français) non bloqué | motifs élargis |
| Demande mixte commande + poème entièrement refusée | routage par proposition |
| Routeur 22/24 | exemples complémentaires |
| Réponse « livraison prévue » pour une commande déjà livrée (non détectée par un simple test de contenu) | contrôle de fidélité aux résultats SQL, nouvelle tentative, gabarit de repli |
| Pour « Où en est ma commande ? » le LLM ajoutait `LIMIT 1` et choisissait une commande au hasard | règle dans le template SQL + exemples : sans numéro, toutes les commandes, puis le bot demande laquelle |
| Une insulte était routée en « demande d'aide », avec un refus parasite | route « mécontentement » + reclassement si la phrase contient des termes de commande |
| Réponse à une question de paiement ne disant pas « payée » | règle dans le prompt système |

## 7. Résultats
- **38 cas, 38 réussis** (23 fonctionnels, 15 sécurité), identiques sur 3 exécutions : statuts invoiced/shipped/delivered, introuvable, plusieurs commandes, comptage, dernière commande, relais humain, hors périmètre, utilisateur agressif, désescalade, anglais ; commande d'un autre client, `user_id=0`, injection, usurpation, prompt leak, SQL malveillant, jeu de rôle, demande de la table `users`, demande de contourner le filtre.
- **Garde-fous SQL : 17/17** (légitimes acceptés ; users, orders, sqlite_master, DROP, DELETE, UPDATE, multi-instructions, ATTACH, PRAGMA, load_extension, UNION, commentaires refusés ; isolation vérifiée).
- **Routeur : 26/26**. Aucune fuite de données personnelles.
- Les traces (dont la **requête SQL générée**) sont dans `resultats/resultats_tests.csv`.

## 8. Démonstration suggérée (3–4 minutes)
1. Notebook `01` : `nvidia-smi`, modèle servi, anomalies `user_id=0`.
2. Notebook `02` : template SQL, requêtes générées par le LLM, une commande de chaque statut → réponse naturelle.
3. Notebook `03` : prompt système, client agressif, relais humain, date absente non inventée.
4. Notebook `04` : routeur, garde-fous SQL, tentatives d'accès à d'autres clients.
5. Notebook `05` : synthèse et critères ; *Restart & Run All* possible en direct (~2 min par exécution).

## 9. Limites et améliorations
- Jeu de tests modeste, écrit par l'auteur ; exemples du routeur complétés après un premier passage (sur-ajustement léger possible) → jeu de validation indépendant.
- Filtre d'injection par motifs non exhaustif ; l'isolation réelle vient du bac à sable SQL → classifieur dédié en complément.
- Réponses non déterministes ; contrôle de fidélité et gabarit de repli limitent le risque → évaluation par un second modèle, plus d'exécutions.
- Authentification simulée → session réelle en production ; pas d'interface web (hors objectif actualisé) → API FastAPI devant `handle()`.
- Paiement : pas de colonne dédiée ; on applique la définition du dossier (invoiced = validée et payée, donc tout statut ultérieur aussi).

## 10. Questions probables
**Le LLM écrit du SQL : n'est-ce pas dangereux ?** Il écrit, mais le code exécute dans un bac à sable (données du seul client, SELECT sur une seule table, liste blanche SQLite). Même un SQL malveillant ne peut rien atteindre d'autre ; 17 tests le démontrent.

**Comment empêchez-vous de voir la commande d'un autre client ?** `user_id` issu de l'authentification, jamais du message ; la table que voit la requête ne contient que ses lignes ; réponse identique à « introuvable ».

**Et si l'injection n'est pas détectée par le filtre ?** Elle n'a aucun pouvoir : isolation SQL, message traité comme donnée, sortie contrôlée.

**Pourquoi un routeur sémantique ?** Il s'exécute avant le LLM principal, est testable séparément (26/26) et réglable (exemples, seuil).

**Comment gérez-vous les hallucinations ?** Faits injectés, interdiction d'inventer, contrôle automatique des dates/numéros/cohérence, repli déterministe ; un cas réel a été détecté et corrigé.

**Où sont les templates de prompts ?** Dossier `prompts/`, détaillé dans `prompts/README.md` ; ils sont chargés par le code, jamais en dur.

**Qu'est-ce qui reste faible ?** Voir §9.

## 11. Où trouver quoi
`README.md` (correspondance avec les 3 étapes), `prompts/`, `notebooks/`, `resultats/`, `RAPPORT.md`, `RUNBOOK_JUPYTERLAB.md`.
