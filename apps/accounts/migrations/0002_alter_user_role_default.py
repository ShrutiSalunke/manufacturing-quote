# Generated manually for Users CRUD defaults
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("ADMIN", "Admin"), ("QUOTER", "Quoter")],
                default="ADMIN",
                max_length=20,
            ),
        ),
    ]
