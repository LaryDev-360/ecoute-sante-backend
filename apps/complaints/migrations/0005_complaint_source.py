# Generated manually for Phase 11

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("complaints", "0004_merge_20260623_1847"),
    ]

    operations = [
        migrations.AddField(
            model_name="complaint",
            name="imported_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="imported_complaints",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="complaint",
            name="registered_on_paper_at",
            field=models.DateField(
                blank=True,
                help_text="Date d'enregistrement sur le registre papier (import staff).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="complaint",
            name="source",
            field=models.CharField(
                choices=[("ONLINE", "En ligne"), ("PAPER", "Dossier papier")],
                default="ONLINE",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="complaint",
            index=models.Index(fields=["source"], name="complaints_c_source_8a1f2d_idx"),
        ),
    ]
