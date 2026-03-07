from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("material", "0001_initial"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="material",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="material",
            constraint=models.UniqueConstraint(fields=("company_id", "code"), name="uq_md_material_company_code"),
        ),
        migrations.AddConstraint(
            model_name="material",
            constraint=models.CheckConstraint(
                check=models.Q(tracking__in=["none", "lot", "serial"]),
                name="ck_md_material_tracking_valid",
            ),
        ),
    ]
