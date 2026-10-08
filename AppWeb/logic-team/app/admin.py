# Registra aqui los modelos para editarlos desde Django Admin (modulo de autoria).
from django.contrib import admin

from .models import Partida, RegistroDecision


class RegistroDecisionInline(admin.TabularInline):
    model = RegistroDecision
    extra = 0
    can_delete = False
    readonly_fields = ("orden", "evento_id", "opcion_id", "correcta", "probabilidad", "tirada")
    fields = readonly_fields


@admin.register(Partida)
class PartidaAdmin(admin.ModelAdmin):
    list_display = ("id", "perfil_nombre", "estado", "hp", "xp", "indice", "puntuacion", "creada")
    list_filter = ("estado",)
    inlines = [RegistroDecisionInline]
