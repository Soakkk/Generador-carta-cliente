"""Persistencia atómica del aviso activo para recuperación de sesión."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .suite_storage import suite_root

SCHEMA = 1


def _ruta(root: str | Path | None = None) -> Path:
    return suite_root(root) / "borrador-avisos.json"


def guardar_borrador(datos: dict[str, Any], root: str | Path | None = None) -> None:
    contenido = {
        "schema": SCHEMA,
        "guardado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "datos": datos,
    }
    config.escribir_json(_ruta(root), contenido)


def leer_borrador(root: str | Path | None = None) -> dict[str, Any] | None:
    contenido = config.leer_json(_ruta(root), None)
    if not isinstance(contenido, dict) or contenido.get("schema") != SCHEMA:
        return None
    datos = contenido.get("datos")
    return datos if isinstance(datos, dict) else None


def borrar_borrador(root: str | Path | None = None) -> None:
    _ruta(root).unlink(missing_ok=True)

