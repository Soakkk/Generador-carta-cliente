"""Formato corporativo único para todos los avisos.

El contenido puede editarse, pero la tipografía, el tamaño y los espacios
no dependen del ordenador ni del usuario. Así todos los PDF de la asesoría
mantienen exactamente la misma identidad visual.
"""
from __future__ import annotations

from dataclasses import dataclass

FUENTE_DEF = "Georgia"
TAMANO_CUERPO_DEF = 10.5
INTERLINEADO_DEF = 115.0   # porcentaje
ESPACIO_PARRAFO_DEF = 6.0  # puntos


@dataclass
class Estilo:
    fuente: str = FUENTE_DEF
    tamano_cuerpo: float = TAMANO_CUERPO_DEF
    interlineado: float = INTERLINEADO_DEF
    espacio_parrafo: float = ESPACIO_PARRAFO_DEF


def cargar() -> Estilo:
    """Devuelve siempre el estilo corporativo, idéntico en todos los equipos."""
    return Estilo()


def guardar(estilo: Estilo) -> None:
    """Compatibilidad con versiones anteriores: el estilo ya no se personaliza."""
    return None


def restablecer() -> Estilo:
    return Estilo()
