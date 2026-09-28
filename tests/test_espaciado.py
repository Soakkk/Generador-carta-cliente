"""Lo que se genera sin pasar por el editor (el lote y las vistas previas de
los diálogos) sale con el mismo espaciado que la vista previa principal."""
from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QTextEdit

from avisos import render, templates
from avisos.estilo import Estilo

_OSCURO = bytes(1 if v < 200 else 0 for v in range(256))
_PERIODO = {"cierre_anual": "4T", "renta_arrend": "RENTA"}


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def sin_plantillas_personalizadas(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(templates, "_overrides_cache", {})


def _filas_con_tinta(img) -> list[int]:
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    datos = bytes(img.constBits()).translate(_OSCURO)
    return [y for y in range(h) if 1 in datos[y * bpl:y * bpl + 4 * w]]


def _html_del_editor(ctx: templates.Contexto, plantilla: templates.Plantilla,
                     est: Estilo) -> str:
    """Lo mismo que hace la ventana principal al cargar el aviso en el editor."""
    editor = QTextEdit()
    fuente = QFont(est.fuente)
    fuente.setPointSizeF(est.tamano_cuerpo)
    editor.document().setDefaultFont(fuente)
    editor.document().setDefaultStyleSheet(render.stylesheet(est))
    editor.setHtml(render.documento_inicial(ctx, plantilla, est))
    render.aplicar_margenes_bloques(editor.document(), est)
    return editor.toHtml()


@pytest.mark.parametrize("plantilla", templates.PLANTILLAS, ids=lambda p: p.id)
def test_el_lote_sale_con_el_espaciado_de_la_vista_previa(qapp, plantilla):
    est = Estilo()
    ctx = templates.Contexto(
        periodo=_PERIODO.get(plantilla.id, "1T"), anio=2026,
        documentos=plantilla.documentos_def, navidad=plantilla.usa_navidad,
        fecha_carta=date(2026, 4, 1),
    )
    principal = render.render_preview_documento(
        _html_del_editor(ctx, plantilla, est), dpi=110, est=est, fecha=date(2026, 4, 1))
    directo = render.render_preview(ctx, plantilla, dpi=110, est=est)
    assert _filas_con_tinta(directo) == _filas_con_tinta(principal)
