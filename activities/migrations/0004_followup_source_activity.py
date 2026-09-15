from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0003_followup_company_and_nullable_archive_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="source_activity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="follow_ups",
                to="activities.activity",
            ),
        ),
    ]
