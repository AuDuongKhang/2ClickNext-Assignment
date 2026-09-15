from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("handoffs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="handoffrun",
            name="should_continue",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="handoffrun",
            name="allowed_scope",
            field=models.CharField(default="none", max_length=32),
        ),
    ]
