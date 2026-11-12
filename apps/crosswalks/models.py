"""
Models for P-code crosswalks (docs/crosswalks.md).

A response, a government or an older COD version often names a country's places with
codes of its own. A Crosswalk is one such set of codes for one country (e.g. the
Hurricane Melissa 5W form's Jamaican codes), and each CrosswalkEntry one of its codes,
mapped to the COD-AB P-code this service holds (or not, yet). The boundaries stay the one
set of codes; a crosswalk only translates into them.

Like apps.boundary_csv, a managed app: the boundary rows themselves stay in cod_adm.
"""

from django.db import models


class Crosswalk(models.Model):
    """One set of codes for one country, e.g. JM / melissa-5w."""

    iso2 = models.CharField(max_length=2)
    key = models.SlugField(max_length=100)
    name = models.CharField(max_length=255)
    # Where the codes come from (a form, a document, a dataset's link)
    source = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("iso2", "key")
        ordering = ["iso2", "key"]

    def __str__(self):
        return f"{self.iso2}/{self.key}"


class CrosswalkEntry(models.Model):
    """One of a crosswalk's codes, and the P-code it is (blank: not matched)."""

    CODE = "code"      # the same code, the same place (its name agrees)
    NAME = "name"      # the same name within its parent's area
    FUZZY = "fuzzy"    # a close name within its parent's area: to confirm
    MANUAL = "manual"  # set by a person
    NONE = "none"      # not matched: to resolve
    METHODS = [(CODE, "Same code"), (NAME, "Same name in its parent"), (FUZZY, "Close name: to confirm"),
               (MANUAL, "Set by hand"), (NONE, "Not matched")]

    crosswalk = models.ForeignKey(Crosswalk, on_delete=models.CASCADE, related_name="entries")
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255, blank=True, default="")
    level = models.SmallIntegerField(null=True, blank=True)
    parent_code = models.CharField(max_length=64, blank=True, default="")
    pcode = models.CharField(max_length=64, blank=True, default="")
    method = models.CharField(max_length=10, choices=METHODS, default=NONE)
    score = models.FloatField(null=True, blank=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("crosswalk", "code")
        ordering = ["level", "code"]

    def __str__(self):
        return f"{self.code} -> {self.pcode or '?'}"
