"""Historial de avisos generados (para consultar que se genero y cuando)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from . import config

_MAX_ENTRADAS = 500


@dataclass
class Entrada:
    fecha_hora: str
    plantilla: str
    periodo: str
    anio: int
    cliente: str
    ruta: str
    plantilla_id: str = ""
    documentos: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    navidad: bool = False
    notas: str = ""
    titulo_tpl: str = ""
    cuerpo_tpl: str = ""


def _ruta() -> Path:
    return config.config_dir() / "historial.json"


def _entrada_valida(dato: object) -> bool:
    if not isinstance(dato, dict):
        return False
    textos_obligatorios = ("fecha_hora", "plantilla", "periodo", "cliente", "ruta")
    if not all(isinstance(dato.get(campo), str) for campo in textos_obligatorios):
        return False
    if not isinstance(dato.get("anio"), int) or isinstance(dato.get("anio"), bool):
        return False
    for campo in ("plantilla_id", "notas", "titulo_tpl", "cuerpo_tpl"):
        if campo in dato and not isinstance(dato[campo], str):
            return False
    for campo in ("documentos", "extras"):
        if campo in dato and (
            not isinstance(dato[campo], list)
            or not all(isinstance(valor, str) for valor in dato[campo])
        ):
            return False
    return "navidad" not in dato or isinstance(dato["navidad"], bool)


def _historial_valido(datos: object) -> bool:
    return isinstance(datos, list) and all(_entrada_valida(dato) for dato in datos)


def cargar() -> list[Entrada]:
    datos = config.leer_json(_ruta(), [], copias=3, validar=_historial_valido)
    permitidas = {f.name for f in fields(Entrada)}
    entradas: list[Entrada] = []
    for dato in datos if isinstance(datos, list) else []:
        try:
            entradas.append(Entrada(**{k: v for k, v in dato.items() if k in permitidas}))
        except Exception:
            continue
    return entradas


def clientes_recientes(limite: int = 8) -> list[str]:
    """Nombres únicos usados más recientemente, del más nuevo al más viejo."""
    vistos: set[str] = set()
    resultado: list[str] = []
    for entrada in reversed(cargar()):
        nombre = entrada.cliente.strip()
        clave = nombre.casefold()
        if not nombre or nombre == "(genérico)" or clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(nombre)
        if len(resultado) >= max(0, limite):
            break
    return resultado


def registrar(plantilla: str, periodo: str, anio: int, cliente: str, ruta: str,
              *, plantilla_id: str = "", documentos: list[str] | None = None,
              extras: list[str] | None = None, navidad: bool = False,
              notas: str = "", titulo_tpl: str = "", cuerpo_tpl: str = "") -> None:
    """Registra un aviso y, cuando esta disponible, una instantanea reutilizable.

    Los argumentos nuevos son opcionales para poder seguir leyendo y creando
    entradas con el formato de las versiones anteriores.
    """
    entradas = cargar()
    entradas.append(Entrada(
        fecha_hora=datetime.now().strftime("%d/%m/%Y %H:%M"),
        plantilla=plantilla,
        periodo=periodo,
        anio=anio,
        cliente=cliente.strip() or "(genérico)",
        ruta=str(ruta),
        plantilla_id=plantilla_id,
        documentos=list(documentos or []),
        extras=list(extras or []),
        navidad=bool(navidad),
        notas=notas,
        titulo_tpl=titulo_tpl,
        cuerpo_tpl=cuerpo_tpl,
    ))
    entradas = entradas[-_MAX_ENTRADAS:]
    config.escribir_json(_ruta(), [asdict(e) for e in entradas], copias=3)
