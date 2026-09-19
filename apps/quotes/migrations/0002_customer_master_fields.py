# Generated manually for Customer → Clients master fields

from django.db import migrations, models


def backfill_customer_codes(apps, schema_editor):
    Customer = apps.get_model("quotes", "Customer")
    for row in Customer.objects.all().order_by("id"):
        if not row.code:
            row.code = f"CLI-{row.pk:04d}"
            row.save(update_fields=["code"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("quotes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="code",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="customer",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="customer",
            name="gstin",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="customer",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="customer",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(backfill_customer_codes, noop_reverse),
        migrations.AlterField(
            model_name="customer",
            name="code",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AlterModelOptions(
            name="customer",
            options={"ordering": ["code"]},
        ),
    ]
