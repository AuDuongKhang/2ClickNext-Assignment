from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("activities", "0004_followup_source_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="legacy_entry_id",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
