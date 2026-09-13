"""Prepara una version nueva de principio a fin.

Uso (desde la raiz del proyecto):
    .venv\\Scripts\\python scripts\\release.py 1.7.0

Hace, en orden:
  1. Actualiza la version en avisos/__init__.py y installer/AvisosEMarin.iss
  2. Ejecuta scripts/test_full.py y pytest; se detiene si falla
  3. Compila el ejecutable con PyInstaller
  4. Compila el instalador con Inno Setup
  5. Crea el zip portable y los SHA-256
  6. Con --publish, publica todos los artefactos con gh

No toca git ni GitHub: el commit, push y release se hacen aparte.
"""
from __future__ import annotations

import re
import argparse
import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ISCC_PREDETERMINADO = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")


def paso(titulo: str) -> None:
    print(f"\n=== {titulo} ===", flush=True)


def actualizar_version(version: str, *, root: Path = RAIZ) -> None:
    paso(f"1/6 Actualizando version a {version}")
    init = root / "avisos" / "__init__.py"
    init.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{version}"',
                           init.read_text("utf-8")), "utf-8")
    iss = root / "installer" / "AvisosEMarin.iss"
    iss.write_text(re.sub(r'#define MyAppVersion "[^"]+"',
                          f'#define MyAppVersion "{version}"',
                          iss.read_text("utf-8")), "utf-8")
    print("  avisos/__init__.py e installer/AvisosEMarin.iss actualizados")


def ejecutar_tests() -> None:
    paso("2/6 Ejecutando pruebas")
    entorno = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    for comando in (
        [sys.executable, "scripts/test_full.py"],
        [sys.executable, "-m", "pytest", "-q"],
    ):
        if subprocess.run(comando, cwd=RAIZ, env=entorno).returncode != 0:
            sys.exit("PRUEBAS FALLIDAS - release cancelada")


def compilar_exe() -> None:
    paso("3/6 Compilando ejecutable (PyInstaller)")
    # Cerrar la app si esta abierta (bloquearia los archivos de dist/)
    subprocess.run(["taskkill", "/IM", "AvisosEMarin.exe", "/F"], capture_output=True)
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                        "AvisosEMarin.spec"], cwd=RAIZ)
    if r.returncode != 0:
        sys.exit("PyInstaller fallo")


def compilar_instalador() -> None:
    paso("4/6 Compilando instalador (Inno Setup)")
    iscc = Path(os.environ.get("ISCC", "")) if os.environ.get("ISCC") else ISCC_PREDETERMINADO
    r = subprocess.run([str(iscc), str(RAIZ / "installer" / "AvisosEMarin.iss")])
    if r.returncode != 0:
        sys.exit("Inno Setup fallo")


def crear_zip(version: str) -> Path:
    paso("5/6 Creando zip portable")
    destino = RAIZ / f"AvisosEMarin_v{version}.zip"
    origen = RAIZ / "dist" / "AvisosEMarin"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for archivo in origen.rglob("*"):
            z.write(archivo, archivo.relative_to(origen))
    print(f"  {destino.name} ({destino.stat().st_size / 1e6:.1f} MB)")
    return destino


def generar_sha256(artefacto: Path) -> Path:
    digestor = hashlib.sha256()
    with artefacto.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digestor.update(bloque)
    destino = artefacto.with_suffix(artefacto.suffix + ".sha256")
    destino.write_text(f"{digestor.hexdigest()}  {artefacto.name}\n", "ascii")
    return destino


def publicar_release(version: str, artefactos: list[Path]) -> None:
    paso("6/6 Publicando release")
    comando = [
        "gh", "release", "create", f"v{version}",
        *(str(path) for path in artefactos),
        "--generate-notes", "--title", f"Avisos E. Marín v{version}",
    ]
    if subprocess.run(comando, cwd=RAIZ).returncode != 0:
        sys.exit("No se pudo publicar el release")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba, construye y publica Avisos E. Marín")
    parser.add_argument("version")
    parser.add_argument("--publish", action="store_true", help="publica con GitHub CLI")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        parser.error("version debe tener formato X.Y.Z")
    version = args.version
    actualizar_version(version)
    ejecutar_tests()
    compilar_exe()
    compilar_instalador()
    portable = crear_zip(version)
    instalador = next((RAIZ / "dist_installer").glob(f"AvisosEMarin_Setup_{version}.exe"))
    artefactos = [instalador, generar_sha256(instalador), portable, generar_sha256(portable)]
    if args.publish:
        publicar_release(version, artefactos)
    print(f"\nLISTO. Artefactos de la v{version}:")
    print(f"  dist_installer/AvisosEMarin_Setup_{version}.exe")
    print(f"  AvisosEMarin_v{version}.zip")
    if not args.publish:
        print("Publicación omitida; usa --publish o el workflow de GitHub Actions.")


if __name__ == "__main__":
    main()
