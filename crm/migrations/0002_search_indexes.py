from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models


def populate_phone_search(apps, schema_editor):
    Contact = apps.get_model("crm", "Contact")
    for contact in Contact.objects.all().iterator():
        contact.phone_search = "".join(character for character in contact.phone if character.isdigit())
        contact.save(update_fields=["phone_search"])


class Migration(migrations.Migration):
    dependencies = [("crm", "0001_initial")]

    operations = [
        TrigramExtension(),
        migrations.AddField(
            model_name="contact",
            name="phone_search",
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
        migrations.RunPython(populate_phone_search, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="company",
            index=GinIndex(fields=["name"], name="company_name_trgm", opclasses=["gin_trgm_ops"]),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=GinIndex(fields=["first_name"], name="contact_first_trgm", opclasses=["gin_trgm_ops"]),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=GinIndex(fields=["last_name"], name="contact_last_trgm", opclasses=["gin_trgm_ops"]),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=GinIndex(fields=["email"], name="contact_email_trgm", opclasses=["gin_trgm_ops"]),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["phone_search"], name="contact_phone_search_idx"),
        ),
    ]
