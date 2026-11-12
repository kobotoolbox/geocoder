"""python manage.py build_crosswalk JM melissa-5w codes.csv --name "..." --source "..." [--level 2=3]

Makes or remakes a crosswalk (docs/crosswalks.md) from a CSV with the columns code, name,
level (optional) and parent_code (optional), matched to the country's boundaries.
Entries set by hand are kept."""

import csv

from django.core.management.base import BaseCommand, CommandError

from apps.crosswalks import services


class Command(BaseCommand):
    help = "Make or remake a P-code crosswalk from a CSV (code, name, level, parent_code)"

    def add_arguments(self, parser):
        parser.add_argument("country")
        parser.add_argument("key")
        parser.add_argument("csv")
        parser.add_argument("--name", default="")
        parser.add_argument("--source", default="")
        parser.add_argument("--level", action="append", default=[], metavar="THEIRS=OURS",
                            help="a level of the set and the boundaries' level it is, e.g. 2=3")

    def handle(self, *args, **o):
        with open(o["csv"], newline="", encoding="utf-8-sig") as f:
            rows = [{"code": r["code"].strip(), "name": (r.get("name") or "").strip(),
                     "level": int(r["level"]) if (r.get("level") or "").strip().isdigit() else None,
                     "parent_code": (r.get("parent_code") or "").strip()} for r in csv.DictReader(f) if r.get("code")]
        try:
            levels = dict(map(int, x.split("=")) for x in o["level"])
            cw, s = services.build(o["country"], o["key"], o["name"], o["source"], rows, levels=levels)
        except ValueError as e:
            raise CommandError(str(e))
        self.stdout.write(f"{cw}: {s['entries']} codes, {s['by_method']}, {s['to_review']} to review")
