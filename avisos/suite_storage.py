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
    datos = config.leer_json(_ruta(root), {"schema_version": SCHEMA, "clientes": {}})
    if not isinstance(datos, dict):
        raise ValueError("El directorio compartido no contiene un objeto JSON")
    clientes = datos.get("clientes")
    if not isinstance(clientes, dict):
        raise ValueError("El directorio compartido no contiene un mapa de clientes")
    if datos.get("schema_version") == SCHEMA:
        return datos
    if datos.get("schema") != SCHEMA:
        raise ValueError("Versión desconocida del directorio compartido")

    # Migración del formato experimental que esta aplicación publicó antes de
    # adoptar el contrato común. Conservamos todos los clientes y metadatos.
    migrado = {clave: valor for clave, valor in datos.items() if clave != "schema"}
    migrado["schema_version"] = SCHEMA
    migrado["clientes"] = {}
    for clave, registro in clientes.items():
        nif = normalizar_nif(clave)
        if not nif or not isinstance(registro, dict):
            continue
        cliente: dict[str, Any] = {
            "nif": nif,
            "metadatos": {},
            "conflictos": {},
        }
        campos = registro.get("campos", {})
        if isinstance(campos, dict):
            for campo, dato in campos.items():
                if not isinstance(dato, dict) or "valor" not in dato:
                    continue
                cliente[campo] = dato["valor"]
                cliente["metadatos"][campo] = {
                    "origen": str(dato.get("origen", "")),
                    "fecha": str(dato.get("actualizado", "")),
                }
        for extra, valor in registro.items():
            if extra != "campos" and extra not in cliente:
                cliente[extra] = valor
        migrado["clientes"][nif] = cliente
    return migrado


def _valor_visible(nif: str, registro_cliente: dict[str, Any]) -> dict[str, Any]:
    visible: dict[str, Any] = {"nif": nif}
    for campo in CAMPOS:
        if campo in registro_cliente:
            visible[campo] = registro_cliente[campo]
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
    entrada = registro["clientes"].setdefault(
        nif, {"nif": nif, "metadatos": {}, "conflictos": {}}
    )
    metadatos = entrada.setdefault("metadatos", {})
    conflictos_guardados = entrada.setdefault("conflictos", {})
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
        anterior = entrada.get(campo)
        meta_anterior = metadatos.get(campo, {})
        if anterior in (None, ""):
            entrada[campo] = valor
            metadatos[campo] = {"origen": origen, "fecha": marca}
            cambio = True
            continue
        if anterior == valor:
            continue

        decision = decisiones.get(campo)
        if decision == "entrante":
            entrada[campo] = valor
            metadatos[campo] = {"origen": origen, "fecha": marca}
            conflictos_guardados.pop(campo, None)
            cambio = True
        elif decision == "existente":
            conflictos_guardados.pop(campo, None)
            cambio = True
            continue
        else:
            alternativas = conflictos_guardados.setdefault(campo, [anterior])
            if valor not in alternativas:
                alternativas.append(valor)
                cambio = True
            conflictos.append(ConflictoCampo(
                campo=campo,
                existente=anterior,
                entrante=valor,
                origen_existente=str(meta_anterior.get("origen", "")),
                origen_entrante=origen,
                actualizado_existente=str(meta_anterior.get("fecha", "")),
                actualizado_entrante=marca,
            ))

    if cambio or not _ruta(root).exists():
        config.escribir_json(_ruta(root), registro)
    return ResultadoFusion(_valor_visible(nif, entrada), conflictos)
