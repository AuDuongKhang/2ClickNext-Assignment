from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0003_case_insensitive_legacy_code_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="legacy_row_id",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
