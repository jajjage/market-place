import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0002_initial"),
        ("transactions", "0012_remove_escrowtransaction_priority"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricenegotiation",
            name="transaction",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="negotiations",
                to="transactions.escrowtransaction",
            ),
        ),
    ]
