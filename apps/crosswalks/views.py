"""
P-code crosswalks (docs/crosswalks.md):

    GET   /api/crosswalks?country=JM                     the country's crosswalks (public)
    GET   /crosswalks/<iso2>/<key>.json | .csv           one, with its entries (public)
    POST  /api/crosswalks                                make or remake one (admin token)
    PATCH /api/crosswalks/<iso2>/<key>/entries/<code>    set an entry's P-code by hand (admin)
"""

import csv
import io

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from . import services
from .models import Crosswalk, CrosswalkEntry

COLUMNS = ["code", "name", "level", "parent_code", "pcode", "method", "score", "note"]


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def crosswalks(request):
    if request.method == "POST":
        if not (request.user and request.user.is_staff):
            return Response({"error": "an admin's token is needed"}, status=403)
        body = request.data
        rows = body.get("rows") or []
        iso2, key = str(body.get("country", "")).upper(), str(body.get("key", "")).strip()
        levels = body.get("levels") or {}
        if not isinstance(levels, dict) or not all(str(k).isdigit() and str(v).isdigit() for k, v in levels.items()):
            return Response({"error": 'levels maps the set\'s levels to the boundaries\', e.g. {"2": 3}'}, status=400)
        if len(iso2) != 2 or not key or not isinstance(rows, list) or not rows:
            return Response({"error": "country (ISO2), key and rows ([{code, name, level, parent_code}]) are needed"},
                            status=400)
        bad = [r for r in rows if not isinstance(r, dict) or not str(r.get("code") or "").strip()]
        if bad:
            return Response({"error": "every row needs a code", "rows": bad[:5]}, status=400)
        rows = [{"code": str(r["code"]).strip(), "name": str(r.get("name") or "").strip(),
                 "level": int(r["level"]) if str(r.get("level", "")).strip().lstrip("-").isdigit() else None,
                 "parent_code": str(r.get("parent_code") or "").strip()} for r in rows]
        try:
            cw, summary = services.build(iso2, key, body.get("name", ""), body.get("source", ""), rows,
                                         levels=body.get("levels") or None)
        except ValueError as e:
            return Response({"error": str(e)}, status=404)
        return Response({"country": cw.iso2, "key": cw.key, **summary}, status=201)
    iso2 = request.GET.get("country", "").upper()
    qs = Crosswalk.objects.all()
    if iso2:
        qs = qs.filter(iso2=iso2)
    return Response({"crosswalks": [services.crosswalk_json(cw, entries=False) for cw in qs]})


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
@permission_classes([AllowAny])
def crosswalk_export(request, iso2, key, fmt):
    cw = Crosswalk.objects.filter(iso2=iso2.upper(), key=key).first()
    if cw is None:
        return Response({"error": f"no crosswalk {iso2.upper()}/{key}"}, status=404)
    if fmt == "json":
        return Response(services.crosswalk_json(cw))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(COLUMNS)
    for e in cw.entries.all():
        d = services.entry_json(e)
        w.writerow(["" if d[c] is None else d[c] for c in COLUMNS])
    resp = HttpResponse(out.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{cw.iso2}_{cw.key}.csv"'
    return resp


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["PATCH"])
@permission_classes([IsAdminUser])
def crosswalk_entry(request, iso2, key, code):
    e = CrosswalkEntry.objects.filter(crosswalk__iso2=iso2.upper(), crosswalk__key=key, code=code).first()
    if e is None:
        return Response({"error": f"no entry {code} in {iso2.upper()}/{key}"}, status=404)
    pcode = str(request.data.get("pcode") or "").strip()
    if pcode and pcode not in {a["pcode"] for a in services.country_areas(iso2.upper())}:
        return Response({"error": f"{pcode}: not one of {iso2.upper()}'s P-codes"}, status=400)
    e.pcode, e.method, e.score = pcode, CrosswalkEntry.MANUAL if pcode else CrosswalkEntry.NONE, None
    e.note = str(request.data.get("note") or ("set by hand" if pcode else "cleared by hand"))
    e.save()
    e.crosswalk.save()
    return Response(services.entry_json(e))
