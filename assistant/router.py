"""Routage sémantique : classe la demande AVANT tout appel au LLM principal.
Similarité cosinus (embeddings multilingues) avec des exemples par route."""
import numpy as np
from .config import EMBED_MODEL
from .prompts import json_file

ROUTES = json_file("router_examples.json")  # exemples par route (prompts/router_examples.json)
THRESHOLD = 0.30  # sous ce score, la demande est jugée hors périmètre

_model = None
_index = None


def _load():
    global _model, _index
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
        labels, texts = [], []
        for r, ex in ROUTES.items():
            labels += [r] * len(ex)
            texts += ex
        emb = _model.encode(texts, normalize_embeddings=True)
        _index = (np.array(labels), emb)
    return _model, _index


def route(message: str):
    """Retourne (route, score, scores_par_route)."""
    model, (labels, emb) = _load()
    q = model.encode([message], normalize_embeddings=True)[0]
    sims = emb @ q
    scores = {r: float(sims[labels == r].max()) for r in ROUTES}
    best = max(scores, key=scores.get)
    if scores[best] < THRESHOLD:
        best = "off_topic"
    return best, scores[best], scores


def split_segments(message: str):
    """Découpe un message en propositions (phrases) pour traiter les demandes mixtes."""
    import re
    parts = [p.strip() for p in re.split(r"(?<=[.?!;])\s+|\n+", message) if len(p.split()) >= 3]
    return parts or [message]
