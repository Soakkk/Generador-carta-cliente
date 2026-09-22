"""Comprobacion de actualizaciones contra los releases de GitHub.

Usa solo la biblioteca estandar (urllib) para no anadir dependencias.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from . import config

_TIMEOUT = 6

ESTADO_INACTIVA = "idle"
ESTADO_COMPROBANDO = "checking"
ESTADO_DESCARGANDO = "downloading"
ESTADO_LISTA = "ready"
ESTADO_ERROR = "error"


@dataclass
class VersionRemota:
    tag: str
    version: tuple[int, int, int]
    url_instalador: str
    url_sha256: str
    notas: str
    sha256: str = ""


def _version_tupla(texto: str) -> tuple[int, int, int]:
    numeros = re.findall(r"\d+", texto)
    partes = [int(n) for n in numeros[:3]]
    while len(partes) < 3:
        partes.append(0)
    return (partes[0], partes[1], partes[2])


def comprobar() -> VersionRemota | None:
    """Consulta la ultima release en GitHub. None si falla o no hay instalador."""
    url = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"
    peticion = urllib.request.Request(
        url, headers={"User-Agent": "AvisosEMarin", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(peticion, timeout=_TIMEOUT) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    tag = datos.get("tag_name", "")
    instalador = ""
    nombre_instalador = ""
    digest_instalador = ""
    assets = datos.get("assets", [])
    for asset in assets:
        nombre = asset.get("name", "")
        if nombre.lower().endswith(".exe") and "setup" in nombre.lower():
            instalador = asset.get("browser_download_url", "")
            nombre_instalador = nombre
            digest = str(asset.get("digest", ""))
            coincidencia = re.fullmatch(r"sha256:([0-9a-fA-F]{64})", digest)
            digest_instalador = coincidencia.group(1).lower() if coincidencia else ""
    sha256 = ""
    esperado = f"{nombre_instalador}.sha256".casefold()
    for asset in assets:
        if str(asset.get("name", "")).casefold() == esperado:
            sha256 = asset.get("browser_download_url", "")
            break
    if not tag or not instalador:
        return None
    return VersionRemota(
        tag=tag, version=_version_tupla(tag),
        url_instalador=instalador, url_sha256=sha256,
        notas=datos.get("body", ""), sha256=digest_instalador)


def hay_actualizacion(version_actual: str, remota: VersionRemota) -> bool:
    return remota.version > _version_tupla(version_actual)


def _leer_url(url: str) -> bytes:
    peticion = urllib.request.Request(url, headers={"User-Agent": "AvisosEMarin"})
    with urllib.request.urlopen(peticion, timeout=20) as respuesta:
        return respuesta.read()


def preparar_instalacion(
    act: VersionRemota,
    destino: str | Path | None = None,
    progreso: Callable[[int], None] | None = None,
) -> Path:
    """Descarga atómicamente el instalador y exige un SHA-256 válido."""
    esperado = act.sha256.lower() if re.fullmatch(r"[0-9a-fA-F]{64}", act.sha256) else ""
    if not esperado:
        if not act.url_sha256:
            raise ValueError("La actualización no incluye un SHA-256 verificable")
        texto_hash = _leer_url(act.url_sha256).decode("utf-8", "replace")
        encontrado = re.search(r"\b([0-9a-fA-F]{64})\b", texto_hash)
        if not encontrado:
            raise ValueError("El archivo SHA-256 de la actualización no es válido")
        esperado = encontrado.group(1).lower()

    base = Path(destino) if destino is not None else Path(tempfile.gettempdir()) / "AvisosEMarin" / "updates"
    etiqueta = re.sub(r"[^0-9A-Za-z._-]+", "_", act.tag).strip("._") or "actualizacion"
    ruta = base if base.suffix.lower() == ".exe" else base / f"AvisosEMarin_Setup_{etiqueta}.exe"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists() and hashlib.sha256(ruta.read_bytes()).hexdigest() == esperado:
        if progreso:
            progreso(100)
        return ruta
    descriptor, nombre_temporal = tempfile.mkstemp(
        prefix=f"{ruta.name}.", suffix=".part", dir=ruta.parent
    )
    os.close(descriptor)
    temporal = Path(nombre_temporal)
    try:
        recibido = ""
        for intento in range(2):
            digestor = hashlib.sha256()
            url_descarga = act.url_instalador
            if intento and url_descarga.lower().startswith(("http://", "https://")):
                separador = "&" if "?" in url_descarga else "?"
                url_descarga += f"{separador}retry={time.time_ns()}"
            peticion = urllib.request.Request(
                url_descarga,
                headers={
                    "User-Agent": "AvisosEMarin",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(peticion, timeout=20) as respuesta:
                total = int(respuesta.headers.get("Content-Length", 0)) or 0
                leido = 0
                with temporal.open("wb") as archivo:
                    while True:
                        bloque = respuesta.read(65536)
                        if not bloque:
                            break
                        archivo.write(bloque)
                        digestor.update(bloque)
                        leido += len(bloque)
                        if progreso and total:
                            progreso(min(99, int(leido * 100 / total)))
            recibido = digestor.hexdigest()
            if recibido == esperado:
                os.replace(temporal, ruta)
                if progreso:
                    progreso(100)
                return ruta
            temporal.unlink(missing_ok=True)
            if progreso:
                progreso(0)
        raise ValueError(
            "La verificación de integridad SHA-256 no coincide después de reintentar")
    except Exception:
        temporal.unlink(missing_ok=True)
        raise
