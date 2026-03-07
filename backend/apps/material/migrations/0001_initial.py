import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="UoM",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("company_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("name", models.CharField(max_length=100)),
                ("symbol", models.CharField(max_length=20)),
                ("ratio_to_base", models.DecimalField(decimal_places=8, max_digits=20)),
            ],
            options={"db_table": "md_uom", "unique_together": {("company_id", "name"), ("company_id", "symbol")}},
        ),
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("company_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("address", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"db_table": "md_warehouse", "unique_together": {("company_id", "code")}},
        ),
        migrations.CreateModel(
            name="MaterialCategory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("company_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("name", models.CharField(max_length=120)),
                (
                    "parent",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="material.materialcategory"),
                ),
            ],
            options={"db_table": "md_material_category", "unique_together": {("company_id", "name", "parent")}},
        ),
        migrations.CreateModel(
            name="Material",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("company_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("spec", models.TextField(blank=True)),
                ("tracking", models.CharField(choices=[("none", "None"), ("lot", "Lot"), ("serial", "Serial")], default="none", max_length=16)),
                ("is_container", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="materials", to="material.materialcategory")),
                ("uom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="materials", to="material.uom")),
            ],
            options={"db_table": "md_material", "unique_together": {("company_id", "code")}},
        ),
        migrations.CreateModel(
            name="WarehouseZone",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("company_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="zones", to="material.warehouse")),
            ],
            options={"db_table": "md_warehouse_zone", "unique_together": {("company_id", "warehouse", "code")}},
        ),
        migrations.CreateModel(
            name="BinLocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("company_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bins", to="material.warehouse")),
                (
                    "zone",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bins", to="material.warehousezone"),
                ),
            ],
            options={"db_table": "md_bin_location", "unique_together": {("company_id", "warehouse", "code")}},
        ),
    ]
