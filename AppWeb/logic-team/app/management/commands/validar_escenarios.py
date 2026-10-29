from django.core.management.base import BaseCommand, CommandError

from app.services import conseguir_vidas, escenarios


class Command(BaseCommand):
    help = (
        "Valida config_juego.json, los escenarios de app/data/escenarios/*.json y las "
        "afirmaciones del CU-06 (app/data/preguntas_vidas.json)."
    )

    def handle(self, *args, **options):
        errores = escenarios.validar()
        if not errores:
            errores = conseguir_vidas.validar()  # CU-06: necesita los escenarios sin errores
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
        preguntas = conseguir_vidas.cargar_preguntas()
        verdaderas = sum(1 for p in preguntas.values() if p["respuesta"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Afirmaciones del CU-06 válidas: {len(preguntas)} ({verdaderas} verdaderas y "
                f"{len(preguntas) - verdaderas} falsas)."
            )
        )
