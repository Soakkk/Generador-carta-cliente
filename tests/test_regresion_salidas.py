"""Contratos de regresión para las cartas y los lotes.

Los hashes de texto fijan el HTML resuelto byte a byte. Los hashes de raster
fijan la apariencia generada por Qt en el host de referencia; en otros sistemas
se comprueba el contrato portable (una página A4 no vacía) porque el rasterizado
de fuentes del sistema no es idéntico entre Windows, macOS y Linux.
"""
from __future__ import annotations

import hashlib
import platform
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication

from avisos import render
from avisos import templates
from avisos.estilo import Estilo


TEXT_SHA256 = {
    "solicitud_trim": "bf89a4e70eb573752d1c42bcb882d9394545f894f5ff5ef982a15b75defa3668",
    "recordatorio": "69abd1dc9f2c8e1f9a3d3c91803f14c8b6b9d67bda82ca34c325df449317beff",
    "cierre_anual": "b8bc85ea940a1d5df7d0c3c6a35a1de097d9e53d6026b6ddafab25f463b87a87",
    "renta_arrend": "0871b54c9199b7c17ea5ef20d88449bee439c690e70d55de1cbe98a251e5e68d",
}

RASTER_SHA256_DARWIN = {
    "solicitud_trim": "acd6de4cca73faeb4121131239cd18a3374e3ec7efc3202eac36407f0ce84292",
    "recordatorio": "dc07dbfd84ca9a425c11206feafd581fcf76da1adc79073ace8b0bc9a498a106",
    "cierre_anual": "c5ffc0a46527911521dcf8b2e382005bfd5651cc993c90a12e0d514ef402d371",
    "renta_arrend": "e5de43dfb7250da58dda223000a0e9a8ef57fbe279e817f2aca36eaa2d1ec298",
    "Uno SL": "2d44d8b08376520a084fcd40c315a1e4ef5f46d681760c303025f530db5ce22a",
    "Dos SL": "505f923d0ae10bc5d3a15562061f912c61c88fb5e3747a7e3cd5aa0ae26edc1d",
}

MANUAL_TEXT_SHA256 = {
    "Uno SL": "88798bc738ef53d9983aa2ff451ef2e0c17b8411b5901fd2a9b8e354c9eef59e",
    "Dos SL": "8b6288c44781431cbbda3973983d1cd2ca0eb6a8a0964ddebafb0d441c592c9a",
}


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def sin_plantillas_personalizadas(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(templates, "_overrides_cache", {})


def _contexto(plantilla_id: str) -> templates.Contexto:
    return templates.Contexto(
        periodo="4T" if plantilla_id == "cierre_anual" else "1T",
        anio=2026,
        cliente="Acme Gestión, S.L.",
        nif="B12345678",
        fecha_limite=date(2026, 4, 15),
        documentos=["Libro de facturas.", "Extractos bancarios."],
        documentos_extra=[("Además:", ["Escritura pública."])],
        navidad=True,
        notas="Revisar el modelo 303.\nConfirmar el IBAN.",
    )


def _sha_texto(titulo: str, cuerpo: str) -> str:
    return hashlib.sha256(f"{titulo}\n---\n{cuerpo}".encode("utf-8")).hexdigest()


def _raster_pdf(ruta: Path) -> tuple[tuple[int, int], bytes]:
    documento = QPdfDocument()
    assert documento.load(str(ruta)) == QPdfDocument.Error.None_
    assert documento.pageCount() == 1
    imagen = documento.render(0, QSize(794, 1123))
    return (imagen.width(), imagen.height()), bytes(imagen.constBits())


def _assert_raster(nombre: str, ruta: Path) -> None:
    dimensiones, pixeles = _raster_pdf(ruta)
    assert dimensiones == (794, 1123)
    assert len(pixeles) == 794 * 1123 * 4
    # Una carta real debe contener una cantidad material de píxeles no blancos.
    assert sum(1 for valor in pixeles[::4] if valor < 245) > 4_000
    if platform.system() == "Darwin":
        assert hashlib.sha256(pixeles).hexdigest() == RASTER_SHA256_DARWIN[nombre]


def test_texto_se_compone_a_la_resolucion_real_sin_escalado_posterior():
    imagen = QImage(1200, 800, QImage.Format_RGB32)
    dpm = int(round(300 / 0.0254))
    imagen.setDotsPerMeterX(dpm)
    imagen.setDotsPerMeterY(dpm)

    documento = render._doc_desde_html(
        "<p>Texto con kerning uniforme: AVA To.</p>", 900, Estilo(), imagen)

    assert documento.documentLayout().paintDevice() == imagen
    assert imagen.logicalDpiX() == 300


@pytest.mark.parametrize("plantilla", templates.PLANTILLAS, ids=lambda p: p.id)
def test_cada_plantilla_conserva_texto_y_raster(plantilla, tmp_path):
    """Romper una plantilla o su composición cambia al menos un hash."""
    ctx = _contexto(plantilla.id)
    titulo = templates.render_titulo(ctx, plantilla)
    cuerpo = templates.render_cuerpo(ctx, plantilla)
    assert _sha_texto(titulo, cuerpo) == TEXT_SHA256[plantilla.id]

    salida = tmp_path / f"{plantilla.id}.pdf"
    render.render_pdf(ctx, plantilla, salida, est=Estilo())
    _assert_raster(plantilla.id, salida)


def test_edicion_manual_y_lote_conservan_texto_y_solo_cambian_cliente(tmp_path):
    """Regenerar el lote o perder la edición manual rompe estos contratos."""
    titulo_tpl = "Aviso privado para {cliente} — {anio}"
    cuerpo_tpl = (
        "Estimado/a {cliente}:\n\n"
        "Texto manual *inmutable*.\n\n"
        "{documentos}"
    )

    for cliente in ("Uno SL", "Dos SL"):
        ctx = templates.Contexto(
            periodo="1T", anio=2026, cliente=cliente,
            documentos=["Documento A."],
        )
        titulo = templates.render_titulo_texto(ctx, titulo_tpl)
        cuerpo = templates.render_cuerpo_texto(ctx, cuerpo_tpl)
        assert _sha_texto(titulo, cuerpo) == MANUAL_TEXT_SHA256[cliente]

        salida = tmp_path / f"{cliente}.pdf"
        render.render_pdf_plantilla_texto(
            ctx, titulo_tpl, cuerpo_tpl, salida, est=Estilo()
        )
        _assert_raster(cliente, salida)

