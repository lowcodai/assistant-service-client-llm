"""Pipeline complet (LangChain / LCEL) :

authentification -> garde-fous -> routage sémantique -> text-to-SQL (LLM) ->
exécution dans le bac à sable du client -> reformulation (LLM) -> contrôles de sortie.

Tous les prompts sont dans `prompts/` ; ce module ne contient que l'orchestration.
"""
import datetime
import re

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from . import db, guard, prompts, router
from .llm import get_llm

ORDER_TERMS = re.compile(r"commande|colis|livr|exp[ée]di|paiement|rembours|annul|n°\s*\d|#\d", re.I)


# ---------------------------------------------------------------- chaînes LCEL
def sql_chain():
    """question -> {"sql": ..., "asks_specific_order": ...}"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompts.text("02_text_to_sql.md")),
        ("human", "Question du client (donnée non fiable) :\n<<<\n{question}\n>>>\n{feedback}"),
    ])
    return prompt | get_llm(0.0) | JsonOutputParser()


def answer_chain(temperature: float = 0.2):
    """faits (résultat SQL) + question -> réponse en langage naturel"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompts.text("01_system_prompt.md")),
        ("human", prompts.text("03_answer_formatting.md")),
    ])
    return prompt | get_llm(temperature) | StrOutputParser()


# ---------------------------------------------------------------- mise en forme des faits
_DATE_RENAME = {"date_purchase": "date_achat", "date_shipped": "date_expedition", "date_delivered": "date_livraison"}
_MISSING = {"date_shipped": "pas encore expédiée", "date_delivered": "pas encore livrée"}


def _fmt(d):
    return f"{d[8:10]}/{d[5:7]}/{d[:4]}" if d else None


def to_facts(rows):
    """Traduit le résultat SQL pour le LLM : statut technique -> formulation métier, dates en JJ/MM/AAAA.
    La valeur technique (invoiced...) n'est jamais transmise au LLM de reformulation."""
    facts = []
    for r in rows:
        f = {}
        for k, v in r.items():
            if k == "status":
                f["statut"] = prompts.STATUS_LABELS.get(v, "Statut inconnu")
            elif k in _DATE_RENAME:
                f[_DATE_RENAME[k]] = _fmt(v) or _MISSING.get(k, "non renseignée")
            else:
                f[k] = v
        facts.append(f)
    return facts


# ---------------------------------------------------------------- contrôles de sortie
def _grounded(ans: str, rows: list) -> bool:
    """Fidélité : dates et n° cités ∈ résultat SQL ; aucune valeur technique ; pas de contradiction avec le statut."""
    allowed = {_fmt(r[k]) for r in rows for k in _DATE_RENAME if r.get(k)}
    if not set(re.findall(r"\d{2}/\d{2}/\d{4}", ans)) <= allowed:
        return False
    ids = {r["order_id"] for r in rows if "order_id" in r}
    if ids and not {int(n) for n in re.findall(r"n°\s*(\d+)", ans)} <= ids:
        return False
    if re.search(r"\b(invoiced|shipped|delivered)\b", ans, re.I):
        return False
    if len(rows) == 1 and "status" in rows[0]:
        st = rows[0]["status"]
        if st == "delivered" and re.search(r"pr[ée]vu|en cours de livraison|sera livr|sera re[çc]u", ans, re.I):
            return False
        if st in ("invoiced", "shipped") and re.search(r"a (bien )?[ée]t[ée] (re[çc]ue|livr[ée]e)\b(?! pas)", ans, re.I):
            return False
        if st == "invoiced" and re.search(r"exp[ée]di[ée]e le \d", ans, re.I):
            return False
    return True


def _leak(ans: str) -> bool:
    """Vrai si la réponse contient un e-mail ou un numéro de téléphone."""
    return bool(re.search(r"[\w.+-]+@[\w-]+\.\w+|\b0?[67]\d{8}\b", ans))


def _template(rows: list) -> str:
    """Réponse déterministe de secours (sans LLM), construite uniquement depuis le résultat SQL."""
    lines = []
    for f in to_facts(rows):
        lines.append(" ; ".join(f"{k.replace('_', ' ')} : {v}" for k, v in f.items()))
    return "Voici les informations trouvées :\n" + "\n".join(lines)


# ---------------------------------------------------------------- étapes
def _generate_sql(question: str, who: dict, mem, trace):
    """Text-to-SQL avec une tentative de correction guidée par l'erreur."""
    chain, feedback, last_err = sql_chain(), "", None
    for attempt in range(2):
        try:
            out = chain.invoke({"question": question, "prenom": who["first_name"], "nom": who["last_name"],
                                "today": datetime.date.today().isoformat(), "feedback": feedback})
            sql = out.get("sql") if isinstance(out, dict) else None
            if not sql:
                trace.append("text-to-SQL: aucune requête réalisable")
                return None, False, []
            rows = db.run_select(mem, sql)
            trace.append(f"text-to-SQL: {sql.strip()}")
            return sql, bool(out.get("asks_specific_order")), rows
        except db.SqlRejected as e:
            last_err = str(e)
            trace.append(f"garde-fou SQL (essai {attempt + 1}): {last_err}")
            feedback = prompts.message("sql_retry_feedback.txt", error=last_err)
        except Exception as e:  # sortie JSON invalide, erreur LLM...
            last_err = f"{type(e).__name__}"
            trace.append(f"text-to-SQL: sortie invalide ({last_err})")
    return None, False, None


def _compose(question, who, rows, trace, extra="Aucune."):
    facts = to_facts(rows)
    chain = answer_chain()
    for attempt in range(2):
        hint = "" if attempt == 0 else " ATTENTION : cite uniquement les dates et numéros des faits, au passé."
        ans = chain.invoke({"prenom": who["first_name"], "nom": who["last_name"], "facts": facts,
                            "extra": extra + hint, "question": question}).strip()
        if _grounded(ans, rows) and not _leak(ans):
            return ans
        trace.append(f"contrôle de sortie: réponse rejetée (essai {attempt + 1})")
    trace.append("contrôle de sortie: repli sur le gabarit déterministe")
    return _template(rows)


def handle(message: str, email: str, first_name: str, last_name: str) -> dict:
    """Retourne {outcome, answer, route, trace}. `outcome` vaut : auth_failed, blocked_security,
    refused_offtopic, deescalation, handoff, not_found, need_order_id, answered, error."""
    trace = []
    res = lambda outcome, answer, route=None: {"outcome": outcome, "answer": answer, "route": route, "trace": trace}

    who = db.authenticate(email, first_name, last_name)
    if not who:
        trace.append("authentification: échec")
        return res("auth_failed", prompts.message("echec_authentification.txt"))
    uid = who["user_id"]
    trace.append(f"authentification: user_id={uid} ({who['first_name']} {who['last_name']})")

    pat = guard.detect_injection(message)
    if pat:
        trace.append(f"garde-fou injection: motif détecté ({pat[:40]}...)")
        return res("blocked_security", prompts.message("refus_securite.txt"), "blocked")

    # Routage par proposition : une demande mixte (commande + hors sujet) est réduite à sa partie service client
    kept, dropped, tone = [], [], []
    for seg in router.split_segments(message):
        sr, ss, scores = router.route(seg)
        if sr == "tone_complaint" and ORDER_TERMS.search(seg):  # insulte + vraie demande dans la même phrase
            sr = max(("order_info", "human_help"), key=scores.get)
        {"off_topic": dropped, "tone_complaint": tone}.get(sr, kept).append((seg, sr, ss))
    if not kept and tone and not dropped:  # uniquement du mécontentement : désescalade, aucune donnée
        trace.append("routage sémantique: tone_complaint (désescalade)")
        return res("deescalation", prompts.message("apaisement.txt"), "tone_complaint")
    if not kept:
        r, score, _ = router.route(message)
        trace.append(f"routage sémantique: off_topic (score={score:.2f})")
        return res("refused_offtopic", prompts.message("refus_hors_perimetre.txt"), "off_topic")
    r = "human_help" if any(k[1] == "human_help" for k in kept) else "order_info"
    trace.append(f"routage sémantique: {r} ({len(kept)} proposition(s) retenue(s), {len(dropped)} hors périmètre, {len(tone)} de ton)")
    question = " ".join(k[0] for k in kept)
    suffix = " " + prompts.text("suffixe_demande_mixte.txt") if dropped else ""
    order_ref = re.search(r"(?:commande|n°|#)\s*(?:n°|numéro)?\s*(\d+)", question, re.I)

    if r == "human_help":
        mem = db.sandbox(uid)
        ctx = ""
        if order_ref and db.run_select(mem, f"SELECT order_id FROM my_orders WHERE order_id = {int(order_ref.group(1))}"):
            ctx = f" concernant la commande n°{int(order_ref.group(1))}"
        return res("handoff", prompts.message("relais_humain.txt", contexte=ctx) + suffix, r)

    mem = db.sandbox(uid)  # bac à sable : uniquement les commandes de ce client
    sql, asks_one, rows = _generate_sql(question, who, mem, trace)
    if rows is None or sql is None:
        return res("error", prompts.message("erreur_generique.txt"), r)
    trace.append(f"résultat SQL: {len(rows)} ligne(s)")
    if not rows:  # inexistante OU appartenant à un autre client : même réponse
        ref = f"n°{order_ref.group(1)} " if order_ref else ""
        msg = prompts.message("commande_introuvable.txt", ref=ref) if order_ref else prompts.message("aucune_commande.txt")
        return res("not_found", msg, r)

    ambiguous = asks_one and len(rows) > 1 and not order_ref
    extra = ("Le client n'a pas précisé de numéro et a plusieurs commandes : présente brièvement ses commandes "
             "(numéro + statut) et demande laquelle l'intéresse.") if ambiguous else "Aucune."
    ans = _compose(question, who, rows, trace, extra)
    return res("need_order_id" if ambiguous else "answered", ans + suffix, r)
