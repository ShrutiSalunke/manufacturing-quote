# Generated manually: allow Quote.customer to be null on permanent client delete

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("quotes", "0002_customer_master_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quote",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="quotes",
                to="quotes.customer",
            ),
        ),
    ]
