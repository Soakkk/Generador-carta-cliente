"""Lugar y fecha de la carta: por defecto la del día, se puede cambiar o quitar."""
from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import QCoreApplication, QDate, QEvent, QTimer
from PySide6.QtWidgets import QApplication

from avisos import render, templates

_OSCURO = bytes(1 if v < 200 else 0 for v in range(256))


def _destruir(ventana) -> None:
    """Sin bucle de eventos, deleteLater() no destruye la ventana: su
    autoguardado del borrador seguiría programado y, al vencer durante la
    prueba siguiente, escribiría en el borrador de esa prueba."""
    for temporizador in ventana.findChildren(QTimer):
        temporizador.stop()
    ventana.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


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


def test_la_fecha_es_la_del_dia_salvo_que_se_cambie_o_se_quite():
    assert render.fecha_de(templates.Contexto()) == date(2026, 4, 1)
    assert render.fecha_de(templates.Contexto(fecha_carta=date(2026, 3, 20))) == date(2026, 3, 20)
    assert render.fecha_de(templates.Contexto(con_fecha=False)) is None
    assert render.texto_fecha(date(2026, 4, 1)) == "Murcia, 1 de abril de 2026"


def test_los_pdf_llevan_la_fecha_del_contexto(qapp, tmp_path, monkeypatch):
    recibidas = []
    pintar = render.pintar_documento

    def espia(*args, fecha=None, **kwargs):
        recibidas.append(fecha)
        return pintar(*args, fecha=fecha, **kwargs)

    monkeypatch.setattr(render, "pintar_documento", espia)
    render.render_pdf(templates.Contexto(fecha_carta=date(2026, 3, 20)),
                      templates.PLANTILLAS[0], tmp_path / "uno.pdf")
    render.render_pdf_plantilla_texto(templates.Contexto(con_fecha=False),
                                      "Aviso", "Texto.", tmp_path / "lote.pdf")
    assert recibidas == [date(2026, 3, 20), None]


def _primera_tinta_bajo_la_cabecera_mm(img) -> float | None:
    """mm desde la línea dorada de la cabecera hasta la primera tinta en los
    últimos 5 mm por la derecha del texto, donde acaba «Murcia, …». El título,
    centrado, no llega; el primer párrafo sí, pero mucho más abajo."""
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    px_mm = w / render.A4_W_MM
    datos = bytes(img.constBits()).translate(_OSCURO)

    def tinta(y: int, x0: int, x1: int) -> bool:
        return 1 in datos[y * bpl + 4 * x0:y * bpl + 4 * x1]

    x_linea = int(20 * px_mm)   # sobre la línea dorada, fuera del logo y del texto
    linea = next(y for y in range(h // 3) if tinta(y, x_linea, x_linea + 1))
    bajo_linea = next(y for y in range(linea, h) if not tinta(y, x_linea, x_linea + 1))
    x1 = int((render.A4_W_MM - render.MARGEN_X - render.SANGRIA_TEXTO) * px_mm)
    x0 = x1 - int(5 * px_mm)
    for y in range(bajo_linea, h // 2):
        if tinta(y, x0, x1):
            return (y - linea) / px_mm
    return None


def test_la_linea_de_fecha_solo_se_dibuja_si_esta_activa(qapp):
    plantilla = templates.PLANTILLAS[0]
    con = render.render_preview(templates.Contexto(), plantilla, dpi=150)
    sin = render.render_preview(templates.Contexto(con_fecha=False), plantilla, dpi=150)
    distancia_con = _primera_tinta_bajo_la_cabecera_mm(con)
    distancia_sin = _primera_tinta_bajo_la_cabecera_mm(sin)
    assert distancia_con is not None and distancia_con < 8
    assert distancia_sin is None or distancia_sin > 12


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
        try:
            assert otra.chk_fecha_carta.isChecked() is False
            assert otra.date_carta.isEnabled() is False
        finally:
            _destruir(otra)
    finally:
        _destruir(win)


def test_el_lote_fija_la_misma_fecha_para_toda_la_serie(qapp, tmp_path, monkeypatch):
    from avisos.ui.lote import LoteDialog

    destino = tmp_path / "pdf"
    destino.mkdir()
    dialogo = LoteDialog(None, templates.Contexto(), templates.PLANTILLAS[0], str(destino))
    dialogo._iniciar_lote(["Uno SL", "Dos SL"])
    assert dialogo._lote.configuracion["con_fecha"] is True
    assert dialogo._lote.configuracion["fecha_carta"] == "2026-04-01"
    _destruir(dialogo)

    # Al reanudar la serie otro día se mantiene la fecha con la que empezó.
    monkeypatch.setattr(render, "fecha_carta", lambda: date(2026, 4, 2))
    reanudado = LoteDialog(None, templates.Contexto(), templates.PLANTILLAS[0], str(destino))
    assert reanudado._ctx_base.fecha_carta == date(2026, 4, 1)
    _destruir(reanudado)
