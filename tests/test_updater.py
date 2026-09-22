from __future__ import annotations

import hashlib
import io
import json

import pytest
from PySide6.QtWidgets import QApplication

from avisos import templates
from avisos.app import MainWindow
from avisos.draft import leer_borrador
from avisos.updater import (
    ESTADO_ERROR,
    ESTADO_LISTA,
    VersionRemota,
    comprobar,
    preparar_instalacion,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _version_local(instalador, sha) -> VersionRemota:
    return VersionRemota(
        tag="v2.0.0",
        version=(2, 0, 0),
        url_instalador=instalador.as_uri(),
        url_sha256=sha.as_uri(),
        notas="Prueba local",
    )


def test_preparar_instalacion_descarga_y_valida_sha_real(tmp_path):
    """Aceptar bytes distintos permitiría instalar un artefacto incorrecto."""
    origen = tmp_path / "origen.exe"
    contenido = b"instalador firmado de prueba"
    origen.write_bytes(contenido)
    sha = tmp_path / "origen.exe.sha256"
    sha.write_text(f"{hashlib.sha256(contenido).hexdigest()}  origen.exe\n", "ascii")

    destino = preparar_instalacion(
        _version_local(origen, sha), destino=tmp_path / "descargas"
    )

    assert destino.read_bytes() == contenido
    assert destino.name == "AvisosEMarin_Setup_v2.0.0.exe"
    assert not destino.with_suffix(".exe.part").exists()


def test_preparar_instalacion_elimina_descarga_si_sha_no_coincide(tmp_path):
    """Una descarga corrupta no debe quedar marcada como lista."""
    origen = tmp_path / "origen.exe"
    origen.write_bytes(b"contenido corrupto")
    sha = tmp_path / "origen.exe.sha256"
    sha.write_text(f"{'0' * 64}  origen.exe\n", "ascii")

    with pytest.raises(ValueError, match="SHA-256"):
        preparar_instalacion(_version_local(origen, sha), destino=tmp_path / "descargas")
    assert not (tmp_path / "descargas" / "AvisosEMarin_Setup_v2.0.0.exe").exists()


def test_release_asocia_el_hash_al_exe_seleccionado(monkeypatch):
    class Respuesta:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self):
            return json.dumps({
                "tag_name": "v2.0.0",
                "assets": [
                    {"name": "AvisosEMarin_Setup_2.0.0.exe", "browser_download_url": "setup.exe",
                     "digest": f"sha256:{'a' * 64}"},
                    {"name": "AvisosEMarin_Setup_2.0.0.exe.sha256", "browser_download_url": "setup.sha"},
                    {"name": "AvisosEMarin_portable.zip.sha256", "browser_download_url": "zip.sha"},
                ],
            }).encode()

    monkeypatch.setattr("avisos.updater.urllib.request.urlopen", lambda *_a, **_k: Respuesta())
    remota = comprobar()
    assert remota is not None
    assert remota.url_instalador == "setup.exe"
    assert remota.url_sha256 == "setup.sha"
    assert remota.sha256 == "a" * 64


def test_digest_de_github_evitar_checksum_auxiliar_desactualizado(tmp_path):
    origen = tmp_path / "origen.exe"
    contenido = b"instalador correcto"
    origen.write_bytes(contenido)
    sha = tmp_path / "origen.exe.sha256"
    sha.write_text(f"{'0' * 64}  origen.exe\n", "ascii")
    version = _version_local(origen, sha)
    version.sha256 = hashlib.sha256(contenido).hexdigest()

    destino = preparar_instalacion(version, destino=tmp_path / "descargas")

    assert destino.read_bytes() == contenido


def test_descarga_sha_incorrecta_reintenta_sin_cache(monkeypatch, tmp_path):
    bueno = b"instalador correcto tras reintento"
    malo = b"respuesta intermedia desactualizada"
    respuestas = [malo, bueno]
    peticiones = []

    class Respuesta:
        def __init__(self, contenido):
            self._flujo = io.BytesIO(contenido)
            self.headers = {"Content-Length": str(len(contenido))}

        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, cantidad=-1): return self._flujo.read(cantidad)

    def abrir(peticion, **_kwargs):
        peticiones.append(peticion)
        return Respuesta(respuestas.pop(0))

    monkeypatch.setattr("avisos.updater.urllib.request.urlopen", abrir)
    version = VersionRemota(
        tag="v2.0.0", version=(2, 0, 0),
        url_instalador="https://example.test/setup.exe", url_sha256="",
        notas="", sha256=hashlib.sha256(bueno).hexdigest(),
    )

    destino = preparar_instalacion(version, destino=tmp_path / "descargas")

    assert destino.read_bytes() == bueno
    assert len(peticiones) == 2
    assert "retry=" in peticiones[1].full_url
    assert peticiones[1].get_header("Cache-control") == "no-cache"


def test_reintento_fallido_conserva_instalador_verificado(monkeypatch, tmp_path):
    origen = tmp_path / "origen.exe"
    bueno = b"instalador bueno"
    origen.write_bytes(bueno)
    sha = tmp_path / "origen.exe.sha256"
    sha.write_text(f"{hashlib.sha256(bueno).hexdigest()}  origen.exe\n", "ascii")
    version = _version_local(origen, sha)
    carpeta = tmp_path / "descargas"
    listo = preparar_instalacion(version, destino=carpeta)

    origen.write_bytes(b"descarga corrupta")
    sha.write_text(f"{'0' * 64}  origen.exe\n", "ascii")
    with pytest.raises(ValueError, match="SHA-256"):
        preparar_instalacion(version, destino=carpeta)

    assert listo.read_bytes() == bueno
    assert not list(carpeta.glob("*.part"))


def test_reutiliza_instalador_ya_verificado_sin_redescargar(monkeypatch, tmp_path):
    origen = tmp_path / "origen.exe"
    contenido = b"instalador listo"
    origen.write_bytes(contenido)
    sha = tmp_path / "origen.exe.sha256"
    sha.write_text(f"{hashlib.sha256(contenido).hexdigest()}  origen.exe\n", "ascii")
    version = _version_local(origen, sha)
    carpeta = tmp_path / "descargas"
    listo = preparar_instalacion(version, destino=carpeta)
    origen.unlink()

    reutilizado = preparar_instalacion(version, destino=carpeta)
    assert reutilizado == listo
    assert reutilizado.read_bytes() == contenido


def test_actualizacion_lista_guarda_sesion_y_reintento_periodico(
    monkeypatch, tmp_path, qapp
):
    """Cerrar para instalar sin borrador o sin reintento perdería trabajo/updates."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(templates, "_overrides_cache", {})
    win = MainWindow()
    win.txt_cliente.setText("Trabajo pendiente")
    win.editor.insertPlainText(" EDICION_SIN_GUARDAR")

    win._actualizacion_lista(str(tmp_path / "actualizacion.exe"))

    assert win._estado_actualizacion == ESTADO_LISTA
    assert win._ruta_update_lista == str(tmp_path / "actualizacion.exe")
    assert "se instalará al cerrar" in win.lbl_estado.text()
    assert "EDICION_SIN_GUARDAR" in leer_borrador()["editor_html"]
    assert win._timer_actualizaciones.interval() == 6 * 60 * 60 * 1000
    assert win._timer_actualizaciones.isActive()

    win._actualizacion_error("sin red")
    assert win._estado_actualizacion == ESTADO_LISTA
    assert win._timer_actualizaciones.isActive()
    win.deleteLater()


def test_estado_listo_bloquea_nuevas_comprobaciones(monkeypatch, tmp_path, qapp):
    win = MainWindow()
    ruta = tmp_path / "actualizacion.exe"
    ruta.write_bytes(b"lista")
    win._actualizacion_lista(str(ruta))
    llamadas: list[bool] = []
    monkeypatch.setattr(
        "avisos.app.comprobar_actualizaciones",
        lambda *_a, **kw: llamadas.append(bool(kw.get("silencioso"))),
    )
    win._comprobar_actualizacion_periodica()
    win._buscar_actualizaciones_manual()
    assert llamadas == []
    assert win._estado_actualizacion == ESTADO_LISTA
    win.deleteLater()


def test_release_sincroniza_version_y_genera_hash(tmp_path):
    """Publicar versiones discordantes o sin checksum rompería el canal."""
    from scripts import release

    (tmp_path / "avisos").mkdir()
    (tmp_path / "installer").mkdir()
    (tmp_path / "avisos" / "__init__.py").write_text('__version__ = "1.0.0"\n', "utf-8")
    (tmp_path / "installer" / "AvisosEMarin.iss").write_text(
        '#define MyAppVersion "1.0.0"\n', "utf-8"
    )
    artefacto = tmp_path / "AvisosEMarin_Setup_2.0.0.exe"
    artefacto.write_bytes(b"release")

    release.actualizar_version("2.0.0", root=tmp_path)
    checksum = release.generar_sha256(artefacto)

    assert '__version__ = "2.0.0"' in (tmp_path / "avisos" / "__init__.py").read_text("utf-8")
    assert '#define MyAppVersion "2.0.0"' in (
        tmp_path / "installer" / "AvisosEMarin.iss"
    ).read_text("utf-8")
    assert checksum.read_text("ascii") == (
        f"{hashlib.sha256(b'release').hexdigest()}  {artefacto.name}\n"
    )
