"""
Matching a set of codes to the COD-AB P-codes (docs/crosswalks.md). Pure functions, no
database: `match(rows, areas)` takes the other set's rows and the country's areas.

Each row is {code, name, level?, parent_code?}; each area {pcode, name, level, parent}.
In order, a row is:

1. "code": the same code as an area whose name agrees (normalised);
2. "name": the only area of that name within its parent's area (the area its parent row
   matched, at any depth below it: a set may skip a level the boundaries have), or in the
   country if it has no parent. Several (a constituency and its community both "Black
   River"): the one at the row's level, as `levels` maps the set's levels to the
   boundaries' (e.g. {2: 3}: its communities are level 3), else, for a row with no rows
   under it, the one with no areas under it;
3. "fuzzy": the only area within its parent's area whose name is close (a ratio of at
   least FUZZY): a suggestion, for a person to confirm;
4. "none": not matched (no area, or several equally good: the note names them).

Parents are matched first, so a row's parent is known when it is matched.
"""

import difflib
import re
import unicodedata

FUZZY = 0.85


def normalise(name):
    """A name for comparing: no accents, case or punctuation; "&" is "and", "Saint" "St"."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"\bste\b", "st", s)
    return re.sub(r"[^a-z0-9]", "", s)


def _depth(row, by_code):
    """How many of its parents are in the set (0: a top row), cycles cut."""
    seen, n, code = set(), 0, row.get("parent_code")
    while code and code in by_code and code not in seen:
        seen.add(code)
        n += 1
        code = by_code[code].get("parent_code")
    return n


def match(rows, areas, levels=None):
    """The rows with pcode, method, score and note, in the order given. levels: the set's
    level to the boundaries' level, e.g. {2: 3}."""
    levels = {int(k): int(v) for k, v in (levels or {}).items()}
    by_pcode = {a["pcode"]: a for a in areas}
    children = {}
    for a in areas:
        children.setdefault(a.get("parent") or "", []).append(a)

    def below(pcode):
        """Every area under pcode (not pcode itself)."""
        out, todo = [], list(children.get(pcode, []))
        while todo:
            a = todo.pop()
            out.append(a)
            todo += children.get(a["pcode"], [])
        return out

    by_code = {r["code"]: r for r in rows}
    has_rows = {r.get("parent_code") for r in rows}
    found = {}
    out = {}
    for r in sorted(rows, key=lambda r: _depth(r, by_code)):
        name = normalise(r.get("name"))
        parent = found.get(r.get("parent_code") or "")
        same = by_pcode.get(r["code"])
        if same and normalise(same["name"]) == name:
            res = {"pcode": same["pcode"], "method": "code", "score": 1.0, "note": ""}
        else:
            pool = below(parent) if parent else areas
            exact = [a for a in pool if normalise(a["name"]) == name]
            if len(exact) > 1 and r.get("level") is not None and r["level"] in levels:
                exact = [a for a in exact if a.get("level") == levels[r["level"]]] or exact
            elif len(exact) > 1 and r["code"] not in has_rows:
                exact = [a for a in exact if a["pcode"] not in children] or exact
            if len(exact) == 1:
                res = {"pcode": exact[0]["pcode"], "method": "name", "score": 1.0, "note": ""}
            elif exact:
                res = {"pcode": "", "method": "none", "score": None,
                       "note": "several areas of that name: " + ", ".join(sorted(a["pcode"] for a in exact))}
            else:
                scored = sorted(((difflib.SequenceMatcher(None, name, normalise(a["name"])).ratio(), a) for a in pool),
                                key=lambda x: -x[0])
                best = [x for x in scored if scored and x[0] == scored[0][0]]
                if scored and scored[0][0] >= FUZZY and len(best) == 1:
                    a = best[0][1]
                    res = {"pcode": a["pcode"], "method": "fuzzy", "score": round(scored[0][0], 3),
                           "note": f'close to "{a["name"]}": to confirm'}
                else:
                    res = {"pcode": "", "method": "none", "score": None,
                           "note": "no area of that name" + (f" in {parent}" if parent else "")}
        if res["pcode"]:
            found[r["code"]] = res["pcode"]
        out[r["code"]] = {**r, **res}
    return [out[r["code"]] for r in rows]


def summary(entries):
    """How many matched each way, and how many are left to a person."""
    counts = {}
    for e in entries:
        counts[e["method"]] = counts.get(e["method"], 0) + 1
    return {"entries": len(entries), "by_method": counts,
            "to_review": counts.get("fuzzy", 0) + counts.get("none", 0)}
