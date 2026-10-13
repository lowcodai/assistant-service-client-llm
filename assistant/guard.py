"""Garde-fous anti-injection de prompt (couche heuristique, avant le LLM)."""
import re

_PATTERNS = [
    r"ignor\w*\s+(\w+\s+){0,3}(instructions|consignes|r[eè]gles|prompt)",
    r"oubli\w*\s+(\w+\s+){0,3}(instructions|consignes|r[eè]gles|prompt)",
    r"ignore\s+(all\s+)?(previous|prior|above)",
    r"(system|syst[eè]me)\s*(prompt|message)",
    r"prompt\s+syst[eè]me|r[ée]p[èe]te\w*\s+(\w+\s+){0,3}(prompt|instructions|consignes)",
    r"(drop|truncate)\s+table|;\s*--|' ?or ?'?1'? ?= ?'?1",
    r"you\s+are\s+now|tu\s+es\s+(d[ée]sormais|maintenant)|agis\s+comme|fais\s+comme\s+si",
    r"mode\s+(d[ée]veloppeur|admin|debug|dan)\b|developer\s+mode|jailbreak",
    r"r[ée]v[eè]le\w*\s+(tes|ton|vos|le)\s+(instructions|prompt|consignes)",
    r"\b(select|insert|update|delete|drop|union)\b.{0,40}\b(from|into|table|set|select)\b",
    r"(donne|affiche|liste|montre)\w*\s+(moi\s+)?(toutes?\s+)?(les\s+)?(commandes|donn[ée]es|clients|utilisateurs)\s+(de\s+)?(tous|des\s+autres|d.autres)",
    r"(adresse|t[ée]l[ée]phone|e-?mail|coordonn[ée]es)\s+(de|du)\s+(l.utilisateur|client)\s+\d+",
    r"(je\s+suis|je\s+suis\s+en\s+r[ée]alit[ée])\s+(l.?administrateur|admin|le\s+d[ée]veloppeur|le\s+support)",
]
_RE = [re.compile(p, re.I | re.S) for p in _PATTERNS]


def detect_injection(message: str):
    """Retourne le motif détecté ou None."""
    for rx in _RE:
        if rx.search(message):
            return rx.pattern
    return None
