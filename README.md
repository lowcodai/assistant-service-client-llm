# Assistant de service client e-commerce basé sur un LLM

Projet de validation de la formation **LLM Engineer** (BLENT) : un assistant qui répond en langage naturel aux questions d'un client **authentifié** sur ses commandes, en interrogeant une base SQLite en temps réel. Réalisé et exécuté sur un **DGX Spark** (GPU NVIDIA GB10) avec un LLM local (`Qwen3.8-27B-NVFP4` servi par vLLM), **LangChain** et des embeddings multilingues pour le routage sémantique.

## Les 3 étapes du projet
| Étape | Réalisation | Où |
|---|---|---|
| **1. Récupération des informations** | Text-to-SQL par le LLM, exécution en temps réel, reformulation en langage naturel (statuts `invoiced/shipped/delivered` traduits, jamais exposés) | [`prompts/02_text_to_sql.md`](prompts/02_text_to_sql.md), [`03_answer_formatting.md`](prompts/03_answer_formatting.md), [`status_mapping.json`](prompts/status_mapping.json) · [notebook 02](notebooks/02_recuperation_et_reformulation.ipynb) |
| **2. Comportement du bot** | Ton adapté à la demande, calme face à l'agressivité, relais humain, exceptions (commande introuvable, informations incomplètes), contexte authentifié (prénom, nom, e-mail) | [`prompts/01_system_prompt.md`](prompts/01_system_prompt.md) + messages `.txt` · [notebook 03](notebooks/03_comportement_et_exceptions.ipynb) |
| **3. Protection des données et routage sémantique** | Routeur sémantique avant le LLM, garde-fous d'injection, SQL exécuté dans un bac à sable ne contenant que les commandes du client | [`assistant/router.py`](assistant/router.py), [`guard.py`](assistant/guard.py), [`db.py`](assistant/db.py) · [notebook 04](notebooks/04_routage_securite.ipynb) |

## Architecture
```
message + identité → garde-fous d'injection → routage sémantique (par proposition)
  → text-to-SQL (prompt | LLM | JsonOutputParser)
  → exécution dans un bac à sable : base mémoire ne contenant QUE les commandes du client (SELECT seul, liste blanche SQLite)
  → faits (statuts traduits) → reformulation (prompt | LLM | StrOutputParser)
  → contrôles de sortie (pas de données personnelles, dates/numéros fidèles au SQL) → réponse / refus / relais humain / désescalade
```

## Structure du dépôt
| Dossier | Contenu |
|---|---|
| [`prompts/`](prompts) | **Templates de prompts** (livrable principal), décrits dans [`prompts/README.md`](prompts/README.md) |
| [`assistant/`](assistant) | Code Python : chargement des prompts, LLM, accès SQL sécurisé, garde-fous, routeur, pipeline LangChain, jeux de tests |
| [`notebooks/`](notebooks) | 6 notebooks **exécutés avec leurs sorties** (`.ipynb`) et exports `.html` |
| [`data/`](data) | Base SQLite `orders.db` (tables `users`, `orders`) et CSV fournis |
| [`resultats/`](resultats) | Résultats des tests : 38 cas (questions, réponses, SQL généré, traces), routeur, garde-fous SQL |
| [`docs/`](docs) | [Rapport](docs/RAPPORT.md), [support de soutenance](docs/SOUTENANCE.md), [runbook JupyterLab](docs/RUNBOOK_JUPYTERLAB.md) |
| [`evidence/`](evidence) | `nvidia-smi` (preuve de l'environnement GPU) |

## Résultats (exécutés sur le DGX Spark)
- **38/38** cas de test (23 fonctionnels, 15 sécurité), identiques sur 3 exécutions consécutives.
- **17/17** garde-fous SQL (requêtes légitimes acceptées ; autres tables, écriture, `ATTACH`, `PRAGMA`, multi-instructions... refusés ; isolation vérifiée).
- **26/26** pour le routeur sémantique. Aucune donnée personnelle dans les réponses.
- Limites assumées : jeu de tests modeste, filtre d'injection par motifs non exhaustif, réponses du LLM non déterministes (voir [docs/RAPPORT.md](docs/RAPPORT.md)).

## Exécution
Prérequis : un LLM compatible OpenAI sur `http://localhost:8000/v1` (variables `LLM_BASE_URL` / `LLM_MODEL` pour changer) et Python 3.12.
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name assistant --display-name "Python 3 (assistant)"
cd notebooks && ../.venv/bin/jupyter lab        # Run All ; 05_tests_et_preuves.ipynb pour les preuves
```
Utilisation en Python :
```python
from assistant.pipeline import handle
r = handle("Où en est ma commande 12 ?", email="...", first_name="...", last_name="...")
print(r["outcome"], r["answer"], r["trace"])
```
Les résultats publiés ont été produits sur le DGX Spark ; sur une autre machine, adaptez `LLM_BASE_URL` et `LLM_MODEL` (les réponses peuvent légèrement varier avec un autre modèle).

## Données
La base fournie par la formation est un jeu **synthétique** (40 clients, 100 commandes ; 3 commandes avec `user_id = 0` volontairement anormales, traitées comme telles).

## Licence
MIT — voir [LICENSE](LICENSE).
