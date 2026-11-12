"""
Tests for P-code crosswalks (apps.crosswalks, docs/crosswalks.md).

The matcher is pure; the API's boundary rows come from cod_adm (not in the sqlite test
DB), so apps.crosswalks.services.country_areas is patched, as the CSV suite patches its
row builder.
"""

import csv
from io import StringIO
from unittest.mock import patch

import pytest

from apps.crosswalks import matching

# Jamaica as the boundaries have it: a parish, a constituency, communities (three levels),
# and Melissa's 5W form's codes for some of the same places (two levels, other codes)
AREAS = [
    {"pcode": "JM", "name": "Jamaica", "level": 0, "parent": ""},
    {"pcode": "JM03", "name": "Kingston", "level": 1, "parent": "JM"},
    {"pcode": "JM11", "name": "Saint Elizabeth", "level": 1, "parent": "JM"},
    {"pcode": "JM1101", "name": "Black River", "level": 2, "parent": "JM11"},
    {"pcode": "JM110101", "name": "Black River", "level": 3, "parent": "JM1101"},
    {"pcode": "JM110102", "name": "Santa Cruz", "level": 3, "parent": "JM1101"},
    {"pcode": "JM110103", "name": "Lacovia", "level": 3, "parent": "JM1101"},
    {"pcode": "JM0301", "name": "Kingston Central", "level": 2, "parent": "JM03"},
    {"pcode": "JM030101", "name": "Allman Town", "level": 3, "parent": "JM0301"},
]
MELISSA = [
    {"code": "JM", "name": "Jamaica", "level": 0, "parent_code": ""},
    {"code": "JM17", "name": "KINGSTON", "level": 1, "parent_code": "JM"},
    {"code": "JM11", "name": "ST.ELIZABETH", "level": 1, "parent_code": "JM"},
    {"code": "JM11008", "name": "Black River", "level": 2, "parent_code": "JM11"},
    {"code": "JM11051", "name": "Santa  Cruz", "level": 2, "parent_code": "JM11"},
    {"code": "JM11060", "name": "Lacovai", "level": 2, "parent_code": "JM11"},
    {"code": "JM17001", "name": "Allman Town", "level": 2, "parent_code": "JM17"},
    {"code": "JM11099", "name": "Nowhere Near", "level": 2, "parent_code": "JM11"},
]


def by_code(rows):
    return {r["code"]: r for r in rows}


def test_normalise():
    assert matching.normalise("ST.ELIZABETH") == matching.normalise("Saint Elizabeth")
    assert matching.normalise("Santa  Cruz") == "santacruz"
    assert matching.normalise("Trelawny & Co") == matching.normalise("Trelawny and Co")
    assert matching.normalise("Pétion-Ville") == "petionville"


def test_match_by_code_name_fuzzy_none():
    out = by_code(matching.match(MELISSA, AREAS))
    assert (out["JM"]["pcode"], out["JM"]["method"]) == ("JM", "code")
    # same code, same place
    assert (out["JM11"]["pcode"], out["JM11"]["method"]) == ("JM11", "code")
    # another code: by its name
    assert (out["JM17"]["pcode"], out["JM17"]["method"]) == ("JM03", "name")
    # a level skipped: found below its parent's area at any depth; the constituency and the
    # community are both Black River: a community (no rows under it) is the area with none
    assert (out["JM11008"]["pcode"], out["JM11008"]["method"]) == ("JM110101", "name")
    assert (out["JM11051"]["pcode"], out["JM11051"]["method"]) == ("JM110102", "name")
    assert (out["JM11060"]["pcode"], out["JM11060"]["method"]) == ("JM110103", "fuzzy")
    assert out["JM11060"]["score"] >= matching.FUZZY
    assert (out["JM17001"]["pcode"], out["JM17001"]["method"]) == ("JM030101", "name")
    assert (out["JM11099"]["pcode"], out["JM11099"]["method"]) == ("", "none")


def test_levels_break_a_tie():
    rows = [{"code": "JM11", "name": "St Elizabeth", "level": 1, "parent_code": ""},
            {"code": "X1", "name": "Black River", "level": 2, "parent_code": "JM11"},
            {"code": "X2", "name": "Lacovia", "level": 3, "parent_code": "X1"}]
    # X1 has a row under it, so no guess: the constituency or the community
    out = by_code(matching.match(rows, AREAS))
    assert out["X1"]["method"] == "none" and "JM1101" in out["X1"]["note"]
    # its level 2 is the boundaries' level 2: the constituency
    out = by_code(matching.match(rows, AREAS, levels={2: 2}))
    assert (out["X1"]["pcode"], out["X1"]["method"]) == ("JM1101", "name")
    assert (out["X2"]["pcode"], out["X2"]["method"]) == ("JM110103", "name")


def test_only_within_its_parent():
    rows = [{"code": "JM17", "name": "Kingston", "parent_code": ""},
            {"code": "K1", "name": "Santa Cruz", "parent_code": "JM17"}]
    out = by_code(matching.match(rows, AREAS))
    assert out["K1"]["method"] == "none"  # Santa Cruz is in St. Elizabeth, not Kingston


def test_parents_first_whatever_the_order():
    out = by_code(matching.match(list(reversed(MELISSA)), AREAS))
    assert out["JM17001"]["pcode"] == "JM030101"


def test_summary():
    s = matching.summary(matching.match(MELISSA, AREAS))
    assert s["entries"] == len(MELISSA)
    assert s["to_review"] == 2  # the fuzzy one, the unknown one


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _post(client, rows=MELISSA, **kw):
    with patch("apps.crosswalks.services.country_areas", return_value=AREAS):
        return client.post("/api/crosswalks", {"country": "JM", "key": "melissa-5w", "name": "Melissa 5W",
                                               "source": "Hurricane Melissa 5W form v1.9", "rows": rows, **kw},
                           format="json")


@pytest.mark.django_db
def test_build_needs_an_admin(api):
    assert _post(api).status_code == 403


@pytest.mark.django_db
def test_build_and_read(auth_api, api):
    r = _post(auth_api)
    assert r.status_code == 201
    assert r.data["entries"] == len(MELISSA) and r.data["to_review"] == 2
    listed = api.get("/api/crosswalks?country=JM").json()["crosswalks"]
    assert [(c["key"], c["entries"]) for c in listed] == [("melissa-5w", len(MELISSA))]
    one = api.get("/crosswalks/JM/melissa-5w.json").json()
    got = {e["code"]: e["pcode"] for e in one["entries"]}
    assert got["JM17"] == "JM03" and one["source"] == "Hurricane Melissa 5W form v1.9"
    rows = list(csv.DictReader(StringIO(api.get("/crosswalks/jm/melissa-5w.csv").content.decode())))
    assert {r["code"]: r["method"] for r in rows}["JM11060"] == "fuzzy"


@pytest.mark.django_db
def test_build_refuses_bad_rows(auth_api):
    assert _post(auth_api, rows=[{"name": "no code"}]).status_code == 400
    assert _post(auth_api, rows=[]).status_code == 400


@pytest.mark.django_db
def test_set_by_hand_and_kept_on_rebuild(auth_api, api):
    _post(auth_api)
    with patch("apps.crosswalks.services.country_areas", return_value=AREAS):
        bad = auth_api.patch("/api/crosswalks/JM/melissa-5w/entries/JM11099", {"pcode": "XX99"}, format="json")
        ok = auth_api.patch("/api/crosswalks/JM/melissa-5w/entries/JM11099", {"pcode": "JM110101"}, format="json")
        refused = api.patch("/api/crosswalks/JM/melissa-5w/entries/JM11099", {"pcode": "JM110101"}, format="json")
    assert bad.status_code == 400 and ok.status_code == 200 and refused.status_code in (401, 403)
    assert ok.data["method"] == "manual"
    _post(auth_api)  # remade: the one set by hand stays
    got = {e["code"]: (e["pcode"], e["method"]) for e in api.get("/crosswalks/JM/melissa-5w.json").json()["entries"]}
    assert got["JM11099"] == ("JM110101", "manual")


@pytest.mark.django_db
def test_unknown_crosswalk_404(api):
    assert api.get("/crosswalks/JM/nope.json").status_code == 404
