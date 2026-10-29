# CU-06 Conseguir vidas: estado del minijuego en la partida (ver services/conseguir_vidas.py).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="partida",
            name="vidas_extra",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
