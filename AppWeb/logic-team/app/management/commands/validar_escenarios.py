from django.core.management.base import BaseCommand, CommandError

from app.services import escenarios


class Command(BaseCommand):
    help = "Valida config_juego.json y los escenarios de app/data/escenarios/*.json."

    def handle(self, *args, **options):
        errores = escenarios.validar()
        if errores:
            for error in errores:
                self.stderr.write(self.style.ERROR(f"- {error}"))
            raise CommandError(f"{len(errores)} error(es) en los escenarios.")
        _, catalogo = escenarios.cargar()
        eventos = catalogo["eventos"].values()
        normales = sum(1 for e in eventos if e["tipo"] == escenarios.NORMAL)
        probabilidad = len(catalogo["eventos"]) - normales
        self.stdout.write(
            self.style.SUCCESS(
                f"Escenarios válidos: {len(catalogo['temas'])} materias, {normales} eventos "
                f"normales y {probabilidad} de probabilidad."
            )
        )
