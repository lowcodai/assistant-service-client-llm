"""Accès aux données.

Le LLM génère du SQL (text-to-SQL), mais il s'exécute dans un **bac à sable en mémoire**
qui ne contient QUE les commandes du client authentifié (table `my_orders`) :
- la requête ne peut physiquement pas atteindre les données d'un autre client ;
- un autorisateur SQLite (liste blanche) n'accepte que SELECT sur `my_orders`
  (pas d'ATTACH, PRAGMA, sqlite_master, autre table, extension, écriture) ;
- une seule instruction, sans commentaire, avec budget de calcul et limite de lignes.
"""
import re
import sqlite3
from .config import DB_PATH

SANDBOX_TABLE = "my_orders"
SANDBOX_COLUMNS = ("order_id", "status", "date_purchase", "date_shipped", "date_delivered")
_ALLOWED_FUNCTIONS = {"count", "sum", "min", "max", "avg", "date", "datetime", "strftime", "julianday",
                      "coalesce", "ifnull", "nullif", "lower", "upper", "length", "abs", "round", "substr",
                      "cast", "typeof", "total", "group_concat", "time", "iif"}


class SqlRejected(Exception):
    """Requête refusée par les garde-fous (le message est réinjectable dans le prompt de correction)."""


def _conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def authenticate(email: str, first_name: str, last_name: str):
    """Résout l'identité authentifiée (email + prénom + nom) en user_id.
    Retourne None si les trois champs ne correspondent pas à un seul client."""
    with _conn() as c:
        rows = c.execute(
            "SELECT user_id, first_name, last_name FROM users WHERE lower(email)=lower(?) "
            "AND lower(first_name)=lower(?) AND lower(last_name)=lower(?)",
            (email.strip(), first_name.strip(), last_name.strip()),
        ).fetchall()
    return dict(rows[0]) if len(rows) == 1 else None


def list_orders(user_id: int):
    """Commandes du client (statut + dates uniquement), utilisé pour les contrôles et les tests."""
    with _conn() as c:
        rows = c.execute(f"SELECT {', '.join(SANDBOX_COLUMNS)} FROM orders WHERE user_id=? "
                         "ORDER BY date_purchase DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def _authorizer(action, arg1, arg2, dbname, source):
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and arg1 == SANDBOX_TABLE and arg2 in SANDBOX_COLUMNS + ("",):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _ALLOWED_FUNCTIONS:
        return sqlite3.SQLITE_OK
    if action == getattr(sqlite3, "SQLITE_RECURSIVE", -1):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def sandbox(user_id: int) -> sqlite3.Connection:
    """Base mémoire éphémère contenant uniquement les commandes de `user_id`."""
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    mem.execute(f"CREATE TABLE {SANDBOX_TABLE}(order_id INTEGER, status TEXT, date_purchase TEXT, "
                "date_shipped TEXT, date_delivered TEXT)")
    mem.executemany(f"INSERT INTO {SANDBOX_TABLE} VALUES (?,?,?,?,?)",
                    [tuple(o[c] for c in SANDBOX_COLUMNS) for o in list_orders(user_id)])
    mem.commit()
    mem.set_authorizer(_authorizer)  # posé après le chargement : lecture seule + liste blanche
    return mem


def run_select(mem: sqlite3.Connection, sql: str, limit: int = 50):
    """Valide puis exécute une requête générée. Lève SqlRejected si elle n'est pas conforme."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        raise SqlRejected("requête vide")
    if not re.match(r"(?is)^(select|with)\b", s):
        raise SqlRejected("seules les requêtes SELECT sont autorisées")
    if ";" in s or "--" in s or "/*" in s:
        raise SqlRejected("une seule instruction, sans commentaire")
    budget = {"n": 0}

    def _guard():
        budget["n"] += 1
        return 1 if budget["n"] > 2000 else 0  # abandonne les requêtes trop coûteuses
    mem.set_progress_handler(_guard, 1000)
    try:
        return [dict(r) for r in mem.execute(s).fetchmany(limit)]
    except sqlite3.Error as e:
        raise SqlRejected(f"{type(e).__name__}: {e}") from e
    finally:
        mem.set_progress_handler(None, 0)
