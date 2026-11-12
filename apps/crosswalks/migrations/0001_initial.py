import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Crosswalk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("iso2", models.CharField(max_length=2)),
                ("key", models.SlugField(max_length=100)),
                ("name", models.CharField(max_length=255)),
                ("source", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["iso2", "key"], "unique_together": {("iso2", "key")}},
        ),
        migrations.CreateModel(
            name="CrosswalkEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("level", models.SmallIntegerField(blank=True, null=True)),
                ("parent_code", models.CharField(blank=True, default="", max_length=64)),
                ("pcode", models.CharField(blank=True, default="", max_length=64)),
                ("method", models.CharField(choices=[("code", "Same code"), ("name", "Same name in its parent"),
                                                     ("fuzzy", "Close name: to confirm"), ("manual", "Set by hand"),
                                                     ("none", "Not matched")], default="none", max_length=10)),
                ("score", models.FloatField(blank=True, null=True)),
                ("note", models.TextField(blank=True, default="")),
                ("crosswalk", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries",
                                                to="crosswalks.crosswalk")),
            ],
            options={"ordering": ["level", "code"], "unique_together": {("crosswalk", "code")}},
        ),
    ]
