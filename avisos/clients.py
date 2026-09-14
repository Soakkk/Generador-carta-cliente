"""Base local de clientes enlazada al directorio común de la suite.

Se guarda en un JSON en la carpeta de configuracion del usuario. Sirve
para autocompletar el campo «Cliente» del formulario y para elegir
destinatarios en la generacion en lote.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import time
from pathlib import Path
from typing import Any

from . import config
from .suite_storage import (
    ConflictoCampo, fusionar_cliente, listar_clientes_comunes, normalizar_nif,
)


@dataclass
class Cliente:
    nombre: str
    nif: str = ""
    direccion: str = ""
    iban: str = ""
    telefono: str = ""
    email: str = ""
    favorito: bool = False
    ultimo_uso: float = 0.0


def _ruta() -> Path:
    return config.config_dir() / "clientes.json"


def _cliente_desde_dict(datos: dict[str, Any]) -> Cliente:
    permitidos = {campo.name for campo in fields(Cliente)}
    return Cliente(**{k: v for k, v in datos.items() if k in permitidos})


def cargar() -> list[Cliente]:
    datos = config.leer_json(_ruta(), [])
    locales: list[Cliente] = []
    for dato in datos if isinstance(datos, list) else []:
        try:
            locales.append(_cliente_desde_dict(dato))
        except Exception:
            continue

    por_clave: dict[str, Cliente] = {}
    for cliente in locales:
        clave = normalizar_nif(cliente.nif) or f"nombre:{cliente.nombre.strip().casefold()}"
        por_clave[clave] = cliente
    try:
        for dato in listar_clientes_comunes():
            comun = _cliente_desde_dict(dato)
            clave = normalizar_nif(comun.nif) or f"nombre:{comun.nombre.strip().casefold()}"
            local = por_clave.get(clave)
            if local is None:
                por_clave[clave] = comun
                continue
            # El directorio común enriquece huecos, pero un conflicto queda
            # para resolución explícita y no pisa el valor local en silencio.
            combinado = asdict(local)
            for campo, valor in asdict(comun).items():
                if combinado.get(campo) in (None, "", 0.0, False) and valor not in (None, ""):
                    combinado[campo] = valor
            por_clave[clave] = Cliente(**combinado)
    except Exception:
        pass
    return sorted(por_clave.values(), key=lambda c: c.nombre.casefold())


def guardar(clientes: list[Cliente]) -> list[tuple[Cliente, ConflictoCampo]]:
    ordenados = sorted(clientes, key=lambda c: c.nombre.lower())
    config.escribir_json(_ruta(), [asdict(c) for c in ordenados])
    conflictos: list[tuple[Cliente, ConflictoCampo]] = []
    for cliente in ordenados:
        if normalizar_nif(cliente.nif):
            try:
                resultado = fusionar_cliente(
                    asdict(cliente), origen="AvisosEMarin",
                    resolver={"favorito": "entrante", "ultimo_uso": "entrante"},
                )
                conflictos.extend((cliente, conflicto) for conflicto in resultado.conflictos)
            except Exception:
                # La base histórica local sigue siendo plenamente funcional
                # si el directorio compartido no está disponible.
                continue
    return conflictos


def resolver_conflictos(cliente: Cliente, resolver: dict[str, str]) -> None:
    """Aplica decisiones explícitas sobre conflictos del directorio común."""
    fusionar_cliente(
        asdict(cliente), origen="AvisosEMarin",
        resolver={"favorito": "entrante", "ultimo_uso": "entrante", **resolver},
    )


def upsert(clientes: list[Cliente], nuevo: Cliente, nombre_original: str = "") -> list[Cliente]:
    """Anade `nuevo`, sustituyendo cualquier cliente con el mismo nombre
    (o con `nombre_original`, si se esta editando y el nombre cambio)."""
    clave_borrar = (nombre_original or nuevo.nombre).strip().lower()
    restantes = [c for c in clientes if c.nombre.strip().lower() != clave_borrar]
    restantes.append(nuevo)
    return restantes


def eliminar(clientes: list[Cliente], nombre: str) -> list[Cliente]:
    clave = nombre.strip().lower()
    return [c for c in clientes if c.nombre.strip().lower() != clave]


def buscar(clientes: list[Cliente], nombre: str) -> Cliente | None:
    clave = nombre.strip().lower()
    nif = normalizar_nif(nombre)
    for c in clientes:
        if c.nombre.strip().lower() == clave or (nif and normalizar_nif(c.nif) == nif):
            return c
    return None


def registrar_uso(nombre_o_nif: str) -> None:
    clientes = cargar()
    encontrado = buscar(clientes, nombre_o_nif)
    if encontrado is None:
        return
    encontrado.ultimo_uso = time.time()
    guardar(clientes)


def asegurar_cliente(nombre: str, nif: str = "") -> bool:
    """Si `nombre` no está ya en la base de datos, lo añade con su NIF.

    El resto de campos se puede completar luego desde «Clientes».
    Devuelve True si se ha anadido un cliente nuevo."""
    nombre = nombre.strip()
    if not nombre:
        return False
    clientes = cargar()
    existente = buscar(clientes, nombre)
    if existente:
        if nif.strip() and not existente.nif.strip():
            existente.nif = nif.strip()
            guardar(clientes)
        return False
    clientes.append(Cliente(nombre=nombre, nif=nif.strip()))
    guardar(clientes)
    return True
