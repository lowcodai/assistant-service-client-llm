# Rapport synthétique

## Architecture
`message + identité authentifiée → garde-fous anti-injection → routage sémantique (par proposition) → text-to-SQL (LLM, chaîne LangChain) → exécution dans un bac à sable ne contenant que les commandes du client → reformulation en langage naturel (LLM) → contrôles de sortie → réponse / refus / relais humain / désescalade`.

## Étape 1 — Récupération des informations
Le LLM traduit la question en `SELECT` (template `prompts/02_text_to_sql.md`, JSON structuré, une correction guidée par l'erreur si la requête est rejetée). La requête est exécutée en temps réel sur les données SQLite du client. Les statuts techniques sont traduits (`status_mapping.json`) **avant** d'être transmis au LLM de reformulation, qui n'en voit donc jamais la valeur encodée ; un contrôle de sortie rejette toute réponse contenant `invoiced/shipped/delivered`.

## Étape 2 — Comportement
`prompts/01_system_prompt.md` : ton adapté à la nature de la demande, calme face à un utilisateur agressif, jamais de date inventée, numéro de commande cité, paiement confirmé, relais humain pour toute action. Une route « mécontentement » du routeur évite qu'une insulte soit prise pour une demande d'aide : message uniquement agressif → désescalade (aucune donnée) ; insulte + vraie demande → la demande est traitée.

## Étape 3 — Protection et routage
- Le routeur sémantique (embeddings multilingues + exemples `router_examples.json`) agit **avant** le LLM principal et rejette le hors périmètre ; il fonctionne par proposition, donc une demande mixte est réduite à sa partie service client.
- Injection de prompt : motifs en amont, message client traité comme donnée non fiable, contrôle de sortie.
- **Accès aux commandes d'autrui** : même si le LLM était manipulé, le SQL s'exécute dans une base mémoire qui ne contient que les commandes du client authentifié ; un autorisateur SQLite en liste blanche n'accepte que `SELECT` sur `my_orders` (pas d'autre table, `sqlite_master`, `ATTACH`, `PRAGMA`, écriture, extension), une instruction, sans commentaire, budget de calcul et limite de lignes.
- Commande inexistante, d'un autre client, ou anormale (`user_id=0` : 54, 71, 78) → même message « introuvable ».

## Résultats (notebook 05, exécuté sur le DGX Spark)
- 38/38 cas (23 fonctionnels, 15 sécurité), identiques sur 3 exécutions consécutives (le LLM n'est pas déterministe) ; 0 donnée personnelle des 40 clients dans les réponses ; réponses fidèles au résultat SQL.
- Garde-fous SQL : 17/17 (requêtes légitimes acceptées, 12 types d'attaques refusés, isolation vérifiée).
- Routeur sémantique : 26/26 sur le jeu dédié.

## Limites
- Jeux de tests modestes, écrits par l'auteur ; routeur dont les exemples ont été complétés après un premier passage (risque léger de sur-ajustement).
- Filtre d'injection par motifs non exhaustif ; la garantie d'isolation repose sur le bac à sable SQL, pas sur ce filtre.
- Réponses du LLM non déterministes ; le contrôle de fidélité limite le risque sans l'annuler (repli sur un gabarit sans LLM).
- Authentification simulée (e-mail + prénom + nom fournis) ; pas de déploiement web (hors objectif actualisé).
