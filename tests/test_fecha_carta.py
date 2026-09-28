"""Lugar y fecha de la carta: por defecto la del día, se puede cambiar o quitar."""
from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import QDate
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication

from avisos import render, templates


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(templates, "_overrides_cache", {})
    monkeypatch.setattr(render, "fecha_carta", lambda: date(2026, 4, 1))


def _texto_pdf(ctx: templates.Contexto, tmp_path) -> str:
    ruta = tmp_path / "carta.pdf"
    render.render_pdf(ctx, templates.PLANTILLAS[0], ruta)
    documento = QPdfDocument()
    assert documento.load(str(ruta)) == QPdfDocument.Error.None_
    return documento.getAllText(0).text()


def test_la_carta_lleva_la_fecha_del_dia_por_defecto(qapp, tmp_path):
    assert "Murcia, 1 de abril de 2026" in _texto_pdf(templates.Contexto(), tmp_path)


def test_la_fecha_de_la_carta_se_puede_cambiar(qapp, tmp_path):
    ctx = templates.Contexto(fecha_carta=date(2026, 3, 20))
    assert "Murcia, 20 de marzo de 2026" in _texto_pdf(ctx, tmp_path)


def test_la_fecha_de_la_carta_se_puede_quitar(qapp, tmp_path):
    texto = _texto_pdf(templates.Contexto(con_fecha=False), tmp_path)
    assert "Murcia," not in texto


def test_el_formulario_permite_cambiar_y_quitar_la_fecha(qapp):
    from avisos.app import MainWindow

    win = MainWindow()
    try:
        assert win.chk_fecha_carta.isChecked() is True
        ctx = win._contexto()
        assert ctx.con_fecha is True and ctx.fecha_carta is None   # la del día

        otro_dia = QDate.currentDate().addDays(-3)
        win.date_carta.setDate(otro_dia)
        assert win._contexto().fecha_carta == date(
            otro_dia.year(), otro_dia.month(), otro_dia.day())
        win.date_carta.setDate(QDate.currentDate())
        assert win._contexto().fecha_carta is None

        win.chk_fecha_carta.setChecked(False)
        assert win._contexto().con_fecha is False
        assert win.date_carta.isEnabled() is False

        # Quitarla es una preferencia: se recuerda al volver a abrir.
        otra = MainWindow()
        assert otra.chk_fecha_carta.isChecked() is False
        assert otra.date_carta.isEnabled() is False
        otra.deleteLater()
    finally:
        win.deleteLater()
        qapp.processEvents()


def test_el_lote_fija_la_misma_fecha_para_toda_la_serie(qapp, tmp_path, monkeypatch):
    from avisos.ui.lote import LoteDialog

    destino = tmp_path / "pdf"
    destino.mkdir()
    dialogo = LoteDialog(None, templates.Contexto(), templates.PLANTILLAS[0], str(destino))
    dialogo._iniciar_lote(["Uno SL", "Dos SL"])
    assert dialogo._lote.configuracion["con_fecha"] is True
    assert dialogo._lote.configuracion["fecha_carta"] == "2026-04-01"
    dialogo.deleteLater()

    # Al reanudar la serie otro día se mantiene la fecha con la que empezó.
    monkeypatch.setattr(render, "fecha_carta", lambda: date(2026, 4, 2))
    reanudado = LoteDialog(None, templates.Contexto(), templates.PLANTILLAS[0], str(destino))
    assert reanudado._ctx_base.fecha_carta == date(2026, 4, 1)
    reanudado.deleteLater()
    qapp.processEvents()
