"""Chargement des templates de prompts depuis le dossier `prompts/` (fichiers .md/.txt/.json).
Les prompts ne sont jamais écrits en dur dans le code."""
import json
from functools import lru_cache
from .config import PROMPTS_DIR


@lru_cache(maxsize=None)
def text(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def message(name: str, **kw) -> str:
    """Message déterministe (refus, relais humain...) issu d'un template .txt."""
    return text(name).format(**kw)


@lru_cache(maxsize=None)
def json_file(name: str):
    return json.loads((PROMPTS_DIR / name).read_text(encoding="utf-8"))


STATUS_LABELS = json_file("status_mapping.json")
