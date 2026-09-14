"""Modelo serializable de una cola de avisos, independiente de Qt."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import config
from .suite_storage import suite_root

ESTADOS = {"pendiente", "generando", "completado", "fallido"}


@dataclass
class BatchItem:
    id: str
    cliente_nif: str
    estado: str = "pendiente"
    salida: str = ""
    error: str = ""
    intentos: int = 0
    nombre: str = ""
    pdf_generado: bool = False
    historial_registrado: bool = False


@dataclass
class BatchState:
    items: list[BatchItem] = field(default_factory=list)
    cancelado: bool = False
    carpeta: str = ""
    modo_salida: str = "pdf"
    configuracion: dict[str, Any] = field(default_factory=dict)

    def por_id(self, item_id: str) -> BatchItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def siguiente(self) -> BatchItem | None:
        if self.cancelado:
            return None
        for item in self.items:
            if item.estado == "pendiente":
                item.estado = "generando"
                item.intentos += 1
                item.error = ""
                return item
        return None

    def marcar_ok(self, item_id: str, salida: str) -> None:
        item = self.por_id(item_id)
        item.estado = "completado"
        item.salida = str(salida)
        item.error = ""

    def marcar_pdf(self, item_id: str, salida: str) -> None:
        item = self.por_id(item_id)
        item.salida = str(salida)
        item.pdf_generado = True

    def marcar_historial(self, item_id: str) -> None:
        self.por_id(item_id).historial_registrado = True

    def marcar_error(self, item_id: str, error: str) -> None:
        item = self.por_id(item_id)
        item.estado = "fallido"
        if not item.pdf_generado:
            item.salida = ""
        item.error = str(error)

    def cancelar(self) -> None:
        self.cancelado = True

    def reanudar(self) -> None:
        self.cancelado = False

    def reintentar_fallidos(self) -> None:
        for item in self.items:
            if item.estado == "fallido":
                item.estado = "pendiente"
                item.error = ""
        self.cancelado = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "items": [asdict(item) for item in self.items],
            "cancelado": self.cancelado,
            "carpeta": self.carpeta,
            "modo_salida": self.modo_salida,
            "configuracion": self.configuracion,
        }

    @classmethod
    def from_dict(cls, datos: dict[str, Any]) -> "BatchState":
        items: list[BatchItem] = []
        for dato in datos.get("items", []) if isinstance(datos, dict) else []:
            if not isinstance(dato, dict):
                continue
            try:
                item = BatchItem(**{
                    clave: dato[clave]
                    for clave in (
                        "id", "cliente_nif", "estado", "salida", "error", "intentos", "nombre",
                        "pdf_generado", "historial_registrado",
                    )
                    if clave in dato
                })
            except (KeyError, TypeError, ValueError):
                continue
            if item.estado not in ESTADOS:
                item.estado = "pendiente"
            # Un proceso interrumpido no pudo confirmar esa salida.
            if item.estado == "generando":
                item.estado = "pendiente"
            items.append(item)
        return cls(
            items=items,
            cancelado=bool(datos.get("cancelado", False)),
            carpeta=str(datos.get("carpeta", "")),
            modo_salida=str(datos.get("modo_salida", "pdf")),
            configuracion=(dict(datos.get("configuracion", {}))
                           if isinstance(datos.get("configuracion"), dict) else {}),
        )


def _ruta(root: str | Path | None = None) -> Path:
    return suite_root(root) / "lote-avisos.json"


def guardar_lote(lote: BatchState, root: str | Path | None = None) -> None:
    config.escribir_json(_ruta(root), lote.to_dict())


def cargar_lote(root: str | Path | None = None) -> BatchState | None:
    datos = config.leer_json(_ruta(root), None)
    if not isinstance(datos, dict) or datos.get("schema") != 1:
        return None
    return BatchState.from_dict(datos)


def borrar_lote(root: str | Path | None = None) -> None:
    _ruta(root).unlink(missing_ok=True)
