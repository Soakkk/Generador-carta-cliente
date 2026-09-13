"""Directorio de clientes compartido por las aplicaciones de la asesoría."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

SCHEMA = 1
CAMPOS = ("nombre", "nif", "direccion", "iban", "telefono", "email", "favorito", "ultimo_uso")


@dataclass(frozen=True)
class ConflictoCampo:
    campo: str
    existente: Any
    entrante: Any
    origen_existente: str
    origen_entrante: str
    actualizado_existente: str
    actualizado_entrante: str


@dataclass(frozen=True)
class ResultadoFusion:
    cliente: dict[str, Any]
    conflictos: list[ConflictoCampo]


def normalizar_nif(nif: str) -> str:
    """Clave estable: mayúsculas y solo caracteres alfanuméricos."""
    return re.sub(r"[^0-9A-Z]", "", str(nif or "").upper())


def suite_root(root: str | Path | None = None) -> Path:
    if root is not None:
        destino = Path(root)
    else:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        destino = Path(base) / "AsesoriaEMarin" / "Suite" if base else Path.home() / "AsesoriaEMarin" / "Suite"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _ruta(root: str | Path | None = None) -> Path:
    return suite_root(root) / "clientes.json"


def _registro(root: str | Path | None = None) -> dict[str, Any]:
    datos = config.leer_json(_ruta(root), {"schema": SCHEMA, "clientes": {}})
    if not isinstance(datos, dict) or datos.get("schema") != SCHEMA:
        return {"schema": SCHEMA, "clientes": {}}
    clientes = datos.get("clientes")
    if not isinstance(clientes, dict):
        return {"schema": SCHEMA, "clientes": {}}
    return {"schema": SCHEMA, "clientes": clientes}


def _valor_visible(nif: str, registro_cliente: dict[str, Any]) -> dict[str, Any]:
    campos = registro_cliente.get("campos", {})
    visible: dict[str, Any] = {"nif": nif}
    for campo in CAMPOS:
        dato = campos.get(campo, {}) if isinstance(campos, dict) else {}
        if isinstance(dato, dict) and "valor" in dato:
            visible[campo] = dato["valor"]
    visible["nif"] = nif
    return visible


def listar_clientes_comunes(root: str | Path | None = None) -> list[dict[str, Any]]:
    registro = _registro(root)
    visibles = [
        _valor_visible(nif, cliente)
        for nif, cliente in registro["clientes"].items()
        if isinstance(cliente, dict)
    ]
    return sorted(visibles, key=lambda c: str(c.get("nombre", "")).casefold())


def fusionar_cliente(
    cliente: dict[str, Any],
    *,
    origen: str,
    actualizado: str | None = None,
    resolver: dict[str, str] | None = None,
    root: str | Path | None = None,
) -> ResultadoFusion:
    """Fusiona por NIF sin sobrescribir diferencias sin una decisión.

    ``resolver`` admite ``"entrante"`` o ``"existente"`` por campo. Sin
    esa decisión, el valor almacenado se conserva y se devuelve el conflicto.
    """
    nif = normalizar_nif(str(cliente.get("nif", "")))
    if not nif:
        raise ValueError("El NIF es obligatorio para compartir un cliente")
    marca = actualizado or datetime.now(timezone.utc).isoformat(timespec="seconds")
    decisiones = resolver or {}
    registro = _registro(root)
    entrada = registro["clientes"].setdefault(nif, {"campos": {}})
    campos = entrada.setdefault("campos", {})
    conflictos: list[ConflictoCampo] = []
    cambio = False

    valores = dict(cliente)
    valores["nif"] = nif
    for campo in CAMPOS:
        if campo not in valores:
            continue
        valor = valores[campo]
        if isinstance(valor, str):
            valor = valor.strip()
        if valor in (None, ""):
            continue
        anterior = campos.get(campo)
        if not isinstance(anterior, dict) or anterior.get("valor") in (None, ""):
            campos[campo] = {"valor": valor, "origen": origen, "actualizado": marca}
            cambio = True
            continue
        if anterior.get("valor") == valor:
            continue

        decision = decisiones.get(campo)
        if decision == "entrante":
            campos[campo] = {"valor": valor, "origen": origen, "actualizado": marca}
            cambio = True
        elif decision == "existente":
            continue
        else:
            conflictos.append(ConflictoCampo(
                campo=campo,
                existente=anterior.get("valor"),
                entrante=valor,
                origen_existente=str(anterior.get("origen", "")),
                origen_entrante=origen,
                actualizado_existente=str(anterior.get("actualizado", "")),
                actualizado_entrante=marca,
            ))

    if cambio or not _ruta(root).exists():
        config.escribir_json(_ruta(root), registro)
    return ResultadoFusion(_valor_visible(nif, entrada), conflictos)

