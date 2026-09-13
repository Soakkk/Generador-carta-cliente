"""Configuracion y manual de estilo (constantes de marca y datos fijos).

Todo lo que define la estetica del aviso vive aqui, de modo que TODOS
los avisos salgan siempre identicos.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Avisos Asesoria E. Marin"
ORG_NAME = "Asesoria E. Marin"
GITHUB_REPO = "Soakkk/Generador-carta-cliente"

# --- Paleta de marca (manual de estilo) ---------------------------------
GREEN = "#2E4A3C"        # verde corporativo (logo)
GREEN_SOFT = "#3C5A49"   # verde para texto secundario
GOLD = "#B8995A"         # dorado/arena (linea "FISCAL Y LABORAL")
INK = "#2B2B2B"          # color del cuerpo de texto
CREAM = "#EDE9D9"        # crema (fondo de marca)
LINE = "#C9C2AC"         # gris-arena para separadores suaves

# --- Datos fijos de la asesoria (pie de pagina) -------------------------
COMPANY_TITULARES = "Ricardo y Elena Ballesteros Marin"
COMPANY_DIRECCION = "C/ Alfaro n.º 11, 2.º B · 30001 Murcia"
COMPANY_TELEFONOS = "Tel. 968 24 93 55 · 651 91 55 02"
COMPANY_EMAIL = "asesoriaemarin@gmail.com"

# --- Tipografia ---------------------------------------------------------
# Fuente estandar del sistema (viene con Windows, no hace falta incrustar
# nada). Se eligio una serif clasica en vez de una variable porque estas
# ultimas pueden salir con un grosor incorrecto (en negrita) al exportar
# a PDF, aunque en pantalla se vean bien.
SERIF_FALLBACK = "Georgia"


def resource_dir() -> Path:
    """Carpeta base de recursos (compatible con PyInstaller)."""
    if getattr(sys, "frozen", False):  # empaquetado
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def asset(*parts: str) -> Path:
    return resource_dir().joinpath("assets", *parts)


def logo_path() -> Path:
    """Ruta del logo. Prefiere PNG (con transparencia) sobre JPG.

    Basta con dejar un archivo cuyo nombre empiece por «EM_logo» en
    la carpeta assets; si hay un .png se usa ese.
    """
    carpeta = resource_dir() / "assets"
    candidatos = []
    if carpeta.exists():
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            candidatos += sorted(carpeta.glob(f"EM_logo*{ext[1:]}"))
    if candidatos:
        # png primero por el orden de extensiones
        return candidatos[0]
    return asset("EM_logo_horizontal_claro.jpg")


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / "AvisosEMarin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_path() -> Path:
    return config_dir() / "settings.json"


def _copia_json(ruta: Path, numero: int) -> Path:
    return ruta.with_suffix(f"{ruta.suffix}.bak{numero}")


def escribir_json(ruta: Path, datos, *, copias: int = 0) -> None:
    """Escritura atomica: primero a un archivo temporal y luego se
    sustituye de golpe, para que un corte de luz o un fallo a mitad de
    escritura no deje corrupto el archivo (clientes, historial, etc.)."""
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), "utf-8")
    for numero in range(max(0, copias), 1, -1):
        anterior = _copia_json(ruta, numero - 1)
        if anterior.exists():
            os.replace(anterior, _copia_json(ruta, numero))
    if copias > 0 and ruta.exists():
        shutil.copy2(ruta, _copia_json(ruta, 1))
    os.replace(tmp, ruta)


def leer_json(ruta: Path, por_defecto, *, copias: int = 0, validar=None):
    for candidata in [ruta, *(_copia_json(ruta, n) for n in range(1, copias + 1))]:
        try:
            datos = json.loads(candidata.read_text("utf-8"))
            if validar is None or validar(datos):
                return datos
        except Exception:
            continue
    return por_defecto
