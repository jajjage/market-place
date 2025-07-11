# Generated by Django 5.1.7 on 2025-06-19 13:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0006_alter_escrowtimeout_transaction"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="escrowtransaction",
            name="amount",
        ),
        migrations.RemoveField(
            model_name="escrowtransaction",
            name="price_by_negotiation",
        ),
        migrations.AddField(
            model_name="escrowtransaction",
            name="price",
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name="escrowtransaction",
            name="quantity",
            field=models.IntegerField(default=1),
        ),
    ]
