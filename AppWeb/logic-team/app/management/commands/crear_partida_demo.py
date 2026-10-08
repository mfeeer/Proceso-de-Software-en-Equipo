from django.core.management.base import BaseCommand, CommandError

from app.services import escenarios, motor_partida
from app.views_personalizar import PERFILES


class Command(BaseCommand):
    help = "Crea una partida de prueba del CU-01 sin pasar por las pantallas de CU-02."

    def add_arguments(self, parser):
        parser.add_argument(
            "--perfil", choices=[p["id"] for p in PERFILES], default=PERFILES[0]["id"]
        )
        parser.add_argument(
            "--temas",
            nargs="+",
            default=[
                "ingenieria-requerimientos:0",
                "ingenieria-requerimientos:1",
                "ingenieria-requerimientos:2",
            ],  # fmt: skip
            help="ids de subtema de CU-02, por ejemplo intro-programacion:0",
        )
        parser.add_argument("--semilla", type=int, help="para repetir la misma partida")

    def handle(self, *args, **options):
        perfil = next(p for p in PERFILES if p["id"] == options["perfil"])
        try:
            partida = motor_partida.crear_partida(
                perfil, options["temas"], semilla=options["semilla"]
            )
        except (escenarios.CatalogoError, motor_partida.ReglaError) as exc:
            raise CommandError(str(exc)) from exc
        total = len(partida.secuencia)
        self.stdout.write(self.style.SUCCESS(f"Partida creada con {total} eventos."))
        self.stdout.write(f"Ábrela en: http://localhost:8000/partida/{partida.id}/")
