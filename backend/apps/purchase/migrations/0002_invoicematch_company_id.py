import uuid

from django.db import migrations, models


LEGACY_INVOICE_MATCH_NAMESPACE = uuid.UUID("8b4d2db4-2c0d-4d78-a2d8-0baf2f1450d7")


def backfill_invoice_match_company_id(apps, schema_editor):
    invoice_match_model = apps.get_model("purchase", "InvoiceMatch")

    for invoice_match in invoice_match_model.objects.select_related("po", "grn").all().iterator():
        company_id = None

        if invoice_match.po_id:
            company_id = invoice_match.po.company_id
        elif invoice_match.grn_id:
            company_id = invoice_match.grn.company_id

        if company_id is None:
            company_id = uuid.uuid5(LEGACY_INVOICE_MATCH_NAMESPACE, f"legacy-invoice-match-{invoice_match.id}")

        invoice_match_model.objects.filter(pk=invoice_match.pk).update(company_id=company_id)


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoicematch",
            name="company_id",
            field=models.UUIDField(db_index=True, null=True),
        ),
        migrations.RunPython(backfill_invoice_match_company_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="invoicematch",
            name="company_id",
            field=models.UUIDField(db_index=True),
        ),
    ]
