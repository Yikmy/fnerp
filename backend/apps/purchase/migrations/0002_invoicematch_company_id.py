import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoicematch",
            name="company_id",
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
    ]
