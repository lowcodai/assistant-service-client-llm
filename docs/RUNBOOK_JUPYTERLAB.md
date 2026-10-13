# Runbook — relancer JupyterLab (projet assistant service client)

Contexte : JupyterLab est installé dans `~/projet_assistant/.venv` sur le DGX Spark (`ssh dgxspark`). Il n'écoute que sur `127.0.0.1:8899` côté Spark ; on y accède depuis le Mac par un tunnel SSH. Le LLM (vLLM) doit répondre sur `localhost:8000` côté Spark.

## 1. Vérifier les prérequis (depuis le Mac)
```bash
ssh dgxspark 'curl -s localhost:8000/v1/models | head -c 120; echo; ls ~/projet_assistant/.venv/bin/jupyter'
```
Si le LLM ne répond pas, le démarrer relève du runbook vLLM du dépôt `itshaker-dgx-spark-V2` (pas de ce projet).

## 2. Démarrer JupyterLab sur le Spark (avec un nouveau token)
```bash
TOKEN=$(openssl rand -hex 16); echo "token=$TOKEN"
ssh dgxspark "cd ~/projet_assistant && nohup .venv/bin/jupyter lab --no-browser --ip=127.0.0.1 --port=8899 --ServerApp.token=$TOKEN --notebook-dir=\$HOME/projet_assistant > jupyter.log 2>&1 < /dev/null &"
```
Notez le token affiché (il n'est pas stocké ailleurs).

## 3. Ouvrir le tunnel SSH (depuis le Mac)
```bash
ssh -f -N -o ExitOnForwardFailure=yes -L 8899:127.0.0.1:8899 dgxspark
```

## 4. Ouvrir dans le navigateur
`http://127.0.0.1:8899/lab/tree/notebooks/05_tests_et_preuves.ipynb?token=<TOKEN>`
Noyau à choisir : **Python 3 (assistant)**. Pour régénérer les preuves : *Kernel → Restart Kernel and Run All Cells* (résultats réécrits dans `~/projet_assistant/resultats/`).

## 5. Diagnostic
| Symptôme | Vérification / action |
|---|---|
| Page inaccessible | Tunnel absent : `lsof -iTCP:8899 -sTCP:LISTEN` ; relancer l'étape 3 |
| « Address already in use » côté Spark | `ssh dgxspark 'pkill -f "jupyter-lab.*8899"'` puis étape 2 |
| Récupérer le token d'un serveur en cours | `ssh dgxspark "pgrep -fa jupyter-lab \| grep -o 'token=[0-9a-f]*'"` |
| Journal du serveur | `ssh dgxspark 'tail -30 ~/projet_assistant/jupyter.log'` |
| Noyau « assistant » absent | `ssh dgxspark 'cd ~/projet_assistant && .venv/bin/python -m ipykernel install --user --name assistant --display-name "Python 3 (assistant)"'` |
| Erreurs de connexion au LLM dans les notebooks | Étape 1 ; variables `LLM_BASE_URL` / `LLM_MODEL` si le port a changé |

## 6. Arrêter proprement
```bash
ssh dgxspark 'pkill -f "jupyter-lab.*8899"'
pkill -f "ssh -f -N.*8899"
```
