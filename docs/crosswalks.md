# P-code crosswalks

A response, a government or an older COD version often names a country's places with
codes of its own. Hurricane Melissa's 5W form, for example, numbers Jamaica's parishes
differently from the COD-AB (Kingston is `JM17` there, `JM03` here) and skips a level
(its communities sit directly under the parishes; COD-AB has 131 areas in between).

The boundaries this service holds stay **the one set of codes**. A **crosswalk** translates
another set into them: one per country and set of codes (`JM` / `melissa-5w`), with an
entry for each of its codes: the P-code it is, and how that was found.

## How a crosswalk is matched

`apps/crosswalks/matching.py`, in order, for each of the set's codes (parents first):

| Method | When |
|---|---|
| `code` | the same code as one of the country's areas, whose name agrees |
| `name` | the only area of that name within its parent's area (at any depth below it, so a skipped level doesn't matter), or in the country for a code with no parent |
| `fuzzy` | the only area within its parent's area with a close name (similarity ≥ 0.85): **a suggestion, to confirm** |
| `manual` | set by a person (kept when the crosswalk is remade) |
| `none` | not matched: no such area, or several equally good (the note names them) |

Names are compared without accents, case or punctuation; `&` is "and", "Saint" is "St".
Where two areas within the parent share the name (a constituency and its community both
"Black River"), a code with no codes under it takes the area with no areas under it; or
say which level of the set is which level of the boundaries (`levels`, e.g. `{"2": 3}`).

Melissa's 790 Jamaican codes: 4 by code, 786 by name, none left to review.

## Making one

From a CSV with the columns `code`, `name`, `level` (optional) and `parent_code`
(optional):

```bash
docker compose exec geocoder python manage.py build_crosswalk JM melissa-5w crosswalks/JM_melissa-5w.csv \
  --name "Hurricane Melissa 5W form (v1.9)" --source "The Hurricane Melissa 5W form's parishes and communities (v1.9)"
```

Or through the API, with an admin's token:

```bash
curl -X POST https://geocoder.example.org/api/crosswalks -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"country": "JM", "key": "melissa-5w", "name": "...", "source": "...",
       "rows": [{"code": "JM17", "name": "KINGSTON", "level": 1, "parent_code": "JM"}, ...]}'
```

`crosswalks/` keeps each crosswalk's source codes (`<ISO2>_<key>.csv`, in the image), so it
can be made again on any instance; `--level 2=3` (`"levels"` in the API) says the set's
level 2 is the boundaries' level 3, when names alone don't tell.

It answers with the counts by method and how many are left to review. Making it again
(new codes, boundaries re-ingested) rematches everything except the entries set by hand.

## Reviewing it

The `fuzzy` and `none` entries are for a person: set an entry's P-code by hand (an admin),
in the Django admin (Crosswalks) or:

```bash
curl -X PATCH https://geocoder.example.org/api/crosswalks/JM/melissa-5w/entries/JM11060 \
  -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" -d '{"pcode": "JM110103"}'
```

A P-code that isn't the country's is refused; an empty one marks the entry not matched.

## Reading it (public)

| | |
|---|---|
| `GET /api/crosswalks?country=JM` | the country's crosswalks, with their counts |
| `GET /crosswalks/JM/melissa-5w.json` | one, with every entry: `code`, `name`, `level`, `parent_code`, `pcode`, `method`, `score`, `note` |
| `GET /crosswalks/JM/melissa-5w.csv` | the same as CSV |

## How kobo-espo uses them

kobo-espo's admin areas are this service's boundaries (`espo/seed/admin_areas.py`). With
`--crosswalk melissa-5w` each area also gets the code the crosswalk gives it (`altPcode`),
so a response's own form or data can be matched on its own codes, and an instance that had
areas under the other codes re-keys them in place. See kobo-espo's manual, "P-codes".
