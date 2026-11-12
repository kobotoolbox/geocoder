"""
A country's areas for matching (from cod_adm), and building a crosswalk.
"""

from django.db import connection, transaction

from . import matching
from .models import Crosswalk, CrosswalkEntry


def country_areas(iso2: str) -> list:
    """Every area of a country, each level: [{pcode, name, level, parent}]."""
    out = {}
    with connection.cursor() as cur:
        for level in range(5):
            parent = f"adm{level - 1}_pcode" if level else "NULL"
            cur.execute(
                f"""
                SELECT DISTINCT adm{level}_pcode, adm{level}_name, {parent}
                FROM cod_adm WHERE iso2 = %s AND adm{level}_pcode IS NOT NULL
                """,
                [iso2],
            )
            for pcode, name, up in cur.fetchall():
                out.setdefault(pcode, {"pcode": pcode, "name": name, "level": level, "parent": up or ""})
    return list(out.values())


@transaction.atomic
def build(iso2: str, key: str, name: str, source: str, rows: list, areas: list | None = None, levels: dict | None = None):
    """Make or remake a crosswalk from its rows; entries set by hand are kept (unless
    their code is gone). Returns (crosswalk, summary)."""
    iso2 = iso2.upper()
    areas = country_areas(iso2) if areas is None else areas
    if not areas:
        raise ValueError(f"{iso2}: no boundaries for this country")
    cw, _ = Crosswalk.objects.update_or_create(iso2=iso2, key=key, defaults={"name": name or key, "source": source or ""})
    manual = {e.code: e for e in cw.entries.filter(method=CrosswalkEntry.MANUAL)}
    matched = matching.match(rows, areas, levels)
    cw.entries.exclude(code__in=list(manual)).delete()
    keep = {r["code"] for r in matched}
    cw.entries.filter(code__in=[c for c in manual if c not in keep]).delete()
    CrosswalkEntry.objects.bulk_create([
        CrosswalkEntry(crosswalk=cw, code=r["code"], name=r.get("name") or "", level=r.get("level"),
                       parent_code=r.get("parent_code") or "", pcode=r["pcode"], method=r["method"],
                       score=r["score"], note=r["note"])
        for r in matched if r["code"] not in manual])
    cw.save()  # its updated_at
    return cw, matching.summary(list(cw.entries.values("method")))


def entry_json(e):
    return {"code": e.code, "name": e.name, "level": e.level, "parent_code": e.parent_code,
            "pcode": e.pcode, "method": e.method, "score": e.score, "note": e.note}


def crosswalk_json(cw, entries=True):
    out = {"country": cw.iso2, "key": cw.key, "name": cw.name, "source": cw.source,
           "updated_at": cw.updated_at.isoformat(),
           **matching.summary(list(cw.entries.values("method")))}
    if entries:
        out["entries"] = [entry_json(e) for e in cw.entries.all()]
    return out
