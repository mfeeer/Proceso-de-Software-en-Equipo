# Entidades del diccionario de datos (WP.12, seccion 3.4).
# Perfil y Tema siguen definidos en app/views_personalizar.py (CU-02) y los escenarios
# (NodoNarrativo, Opcion) viven en app/data/*.json (RNF-MAN-05). En la base de datos se guarda
# lo que genera el jugador: la Partida y su bitacora de decisiones (RegistroDecision).
import uuid

from django.conf import settings
from django.db import models


class Partida(models.Model):
    """Partida de un estudiante. La crea CU-02 (perfil y temas) y se juega en CU-01."""

    EN_CURSO = "en_curso"
    COMPLETADA = "completada"
    DERROTA = "derrota"
    ESTADOS = [
        (EN_CURSO, "En curso"),
        (COMPLETADA, "Completada"),
        (DERROTA, "Derrota (sin vidas)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="partidas",
    )

    # Copia del perfil/antecedente elegido en CU-02.
    perfil_id = models.CharField(max_length=40)
    perfil_nombre = models.CharField(max_length=80)
    perfil_descripcion = models.TextField(blank=True)

    # Estado del jugador (RF-05, RF-21).
    hp_max = models.PositiveSmallIntegerField()
    hp = models.PositiveSmallIntegerField()
    xp = models.PositiveIntegerField(default=0)
    atributos = models.JSONField(default=dict)
    puntos_atributo = models.PositiveSmallIntegerField(default=0)
    puntuacion = models.PositiveIntegerField(default=0)
    aciertos = models.PositiveSmallIntegerField(default=0)
    decisiones = models.PositiveSmallIntegerField(default=0)

    # Historia: subtemas elegidos en CU-02 y la secuencia de eventos de esta partida.
    temas = models.JSONField(default=list)
    secuencia = models.JSONField(default=list)
    indice = models.PositiveSmallIntegerField(default=0)
    semilla = models.BigIntegerField(default=0)

    estado = models.CharField(max_length=12, choices=ESTADOS, default=EN_CURSO)
    logros = models.JSONField(default=list)
    # Resultado de la ultima decision; se muestra hasta que el jugador pasa la pagina.
    resultado_pendiente = models.JSONField(null=True, blank=True)
    # CU-06 Conseguir vidas (app/services/conseguir_vidas.py): conteo de eventos para la
    # sugerencia, preguntas vistas, vidas recuperadas y la ronda en juego.
    vidas_extra = models.JSONField(default=dict, blank=True)

    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada"]

    def __str__(self):
        return f"Partida {self.id} ({self.perfil_nombre}, {self.estado})"


class RegistroDecision(models.Model):
    """Bitacora de decisiones (RF-06). Alimenta el mapa de decisiones de Post Game."""

    partida = models.ForeignKey(Partida, on_delete=models.CASCADE, related_name="registros")
    orden = models.PositiveSmallIntegerField()
    evento_id = models.CharField(max_length=60)
    evento_titulo = models.CharField(max_length=120)
    tema_id = models.CharField(max_length=60)
    subtema_nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=15)
    opcion_id = models.CharField(max_length=10)
    opcion_texto = models.TextField()
    correcta = models.BooleanField()
    probabilidad = models.PositiveSmallIntegerField(null=True, blank=True)
    tirada = models.PositiveSmallIntegerField(null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(fields=["partida", "orden"], name="decision_unica_por_orden"),
        ]

    def __str__(self):
        return f"{self.partida_id} #{self.orden} {self.evento_id} -> {self.opcion_id}"


# ---------------------------------------------------------------- CU05 Cuestionario de tecnicismos
# El registro y el historial son por usuario (SDS 1.3.5). Si nadie inicio sesion se guardan con
# la clave de la sesion del navegador (sesion), para que el modo se pueda jugar en la demo.
class TecnicismoRegistrado(models.Model):
    """Tecnicismo que el jugador ya descubrio en un evento del CU01 (RF-41, CU05-RN02)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tecnicismos_registrados",
    )
    sesion = models.CharField(max_length=40, blank=True, db_index=True)
    tecnicismo_id = models.CharField(max_length=60)
    partida = models.ForeignKey(
        Partida, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registrado"]
        constraints = [
            # Acumulativo y sin duplicados (RN02)
            models.UniqueConstraint(
                fields=["usuario", "tecnicismo_id"],
                condition=models.Q(usuario__isnull=False),
                name="tecnicismo_unico_por_usuario",
            ),
            models.UniqueConstraint(
                fields=["sesion", "tecnicismo_id"],
                condition=models.Q(usuario__isnull=True),
                name="tecnicismo_unico_por_sesion",
            ),
        ]

    def __str__(self):
        return f"{self.usuario_id or self.sesion} -> {self.tecnicismo_id}"


class ResultadoCuestionario(models.Model):
    """Resultado de un cuestionario terminado: historial del usuario (RF-58)."""

    EN_LINEA = "en_linea"
    SINCRONIZADO = "sincronizado"
    ORIGENES = [
        (EN_LINEA, "En línea"),
        (SINCRONIZADO, "Sincronizado después (sin conexión, FE1)"),
    ]

    # El id viaja dentro del token firmado: si el navegador reintenta enviar un resultado
    # pendiente, el servidor no lo guarda dos veces (FE1, RF-60).
    id = models.UUIDField(primary_key=True, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cuestionarios",
    )
    sesion = models.CharField(max_length=40, blank=True, db_index=True)
    fecha = models.DateTimeField()
    puntaje = models.PositiveSmallIntegerField()
    aciertos = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    # Una entrada por pregunta: tecnicismo, tipo, opcion elegida, opcion correcta y si acerto
    respuestas = models.JSONField(default=list)
    origen = models.CharField(max_length=12, choices=ORIGENES, default=EN_LINEA)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Cuestionario {self.id} ({self.puntaje}/100)"
