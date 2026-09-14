from django.db import migrations, models
import django.db.models.deletion


def populate_follow_up_company(apps, schema_editor):
    FollowUp = apps.get_model("activities", "FollowUp")
    for follow_up in FollowUp.objects.select_related("opportunity").iterator():
        if follow_up.opportunity_id is None:
            raise RuntimeError("Existing follow-ups require an opportunity to derive their company")
        follow_up.company_id = follow_up.opportunity.company_id
        follow_up.save(update_fields=["company"])


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_activity_author_followup_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="follow_ups",
                to="crm.company",
            ),
        ),
        migrations.RunPython(populate_follow_up_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="followup",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="follow_ups",
                to="crm.company",
            ),
        ),
        migrations.AlterField(
            model_name="followup",
            name="opportunity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="follow_ups",
                to="opportunities.opportunity",
            ),
        ),
        migrations.AlterField(
            model_name="followup",
            name="due_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
