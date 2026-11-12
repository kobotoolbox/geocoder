from django.contrib import admin

from .models import Crosswalk, CrosswalkEntry


class CrosswalkEntryInline(admin.TabularInline):
    model = CrosswalkEntry
    extra = 0
    fields = ("code", "name", "level", "parent_code", "pcode", "method", "score", "note")


@admin.register(Crosswalk)
class CrosswalkAdmin(admin.ModelAdmin):
    list_display = ("iso2", "key", "name", "updated_at")
    search_fields = ("iso2", "key", "name")
    inlines = [CrosswalkEntryInline]
