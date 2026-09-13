from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QDate
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from avisos import clients
from avisos import history
from avisos import templates
from avisos.app import MainWindow
from avisos.draft import guardar_borrador, leer_borrador
from avisos.ui.clientes import clave_orden_cliente


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def entorno(monkeypatch, tmp_path, qapp):
    appdata = tmp_path / "appdata"
    localappdata = tmp_path / "localappdata"
    destino = tmp_path / "pdf"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))
    monkeypatch.setattr(templates, "_overrides_cache", {})
    return destino


def test_borrador_serializa_y_restaura_edicion_manual_completa(entorno, qapp):
    """Omitir un campo o regenerar el editor perdería trabajo al reiniciar."""
    win = MainWindow()
    win.cmb_plantilla.setCurrentIndex(win.cmb_plantilla.findData("recordatorio"))
    win._set_periodo("2T")
    win.spin_anio.setValue(2026)
    win.date_limite.setDate(QDate(2026, 7, 15))
    win.txt_cliente.setText("Acme SL")
    win.txt_nif.setText("B12345678")
    win._set_docs(["Factura A", "Factura B"])
    win.editor.moveCursor(QTextCursor.End)
    win.editor.textCursor().insertText(" MARCA_MANUAL")
    qapp.processEvents()

    datos = win._serializar_borrador()
    assert datos["plantilla_id"] == "recordatorio"
    assert datos["periodo"] == "2T"
    assert datos["documentos"] == ["Factura A", "Factura B"]
    assert datos["editor_dirty"] is True
    assert "MARCA_MANUAL" in datos["editor_html"]
    guardar_borrador(datos)
    win.deleteLater()
    qapp.processEvents()

    restaurada = MainWindow()
    assert restaurada.txt_cliente.text() == "Acme SL"
    assert restaurada.txt_nif.text() == "B12345678"
    assert restaurada._periodo_actual() == "2T"
    assert restaurada._documentos_actuales() == ["Factura A", "Factura B"]
    assert restaurada._editor_dirty is True
    assert "MARCA_MANUAL" in restaurada.editor.toPlainText()
    restaurada.deleteLater()


def test_autoguardado_usa_debounce_de_300_ms(entorno, qapp):
    """Guardar en cada tecla degradaría el editor; no programarlo perdería cambios."""
    win = MainWindow()
    assert win._timer_borrador.interval() == 300
    win.txt_cliente.setText("Cliente con borrador")
    assert win._timer_borrador.isActive()
    win._timer_borrador.timeout.emit()
    assert leer_borrador()["cliente"] == "Cliente con borrador"
    win.deleteLater()


def test_guardar_y_siguiente_conserva_serie_limpia_cliente_y_registra_una_vez(
    entorno, qapp
):
    """Una segunda generación o limpiar la serie rompería el flujo repetitivo."""
    win = MainWindow()
    win._carpeta_destino = str(entorno)
    win.cmb_plantilla.setCurrentIndex(win.cmb_plantilla.findData("solicitud_trim"))
    win._set_periodo("3T")
    win.spin_anio.setValue(2026)
    win.txt_cliente.setText("Cliente Uno SL")
    win.txt_nif.setText("B87654321")
    win._set_docs(["Documento especial"])
    win.editor.moveCursor(QTextCursor.End)
    win.editor.textCursor().insertText(" TEXTO_PROPIO_SERIE")
    qapp.processEvents()
    plantilla_antes = win.cmb_plantilla.currentData()
    periodo_antes = win._periodo_actual()
    docs_antes = win._documentos_actuales()

    salida = win._guardar_y_siguiente(abrir=False)

    assert isinstance(salida, Path) and salida.exists()
    assert len(history.cargar()) == 1
    assert win.cmb_plantilla.currentData() == plantilla_antes
    assert win._periodo_actual() == periodo_antes
    assert win._documentos_actuales() == docs_antes
    assert win.txt_cliente.text() == ""
    assert win.txt_nif.text() == ""
    assert "TEXTO_PROPIO_SERIE" in win.editor.toPlainText()
    assert win._editor_dirty is True

    win._deshacer_cambio_cliente()
    assert win.txt_cliente.text() == "Cliente Uno SL"
    assert win.txt_nif.text() == "B87654321"
    assert "TEXTO_PROPIO_SERIE" in win.editor.toPlainText()
    win.deleteLater()


def test_recientes_favoritos_y_busqueda_por_nif_persisten(entorno):
    """Perder orden o NIF haría que el buscador no acelere clientes repetidos."""
    base = [
        clients.Cliente(nombre="Zulu SL", nif="B00000001", ultimo_uso=10),
        clients.Cliente(nombre="Alfa SL", nif="B00000002", favorito=True, ultimo_uso=1),
    ]
    clients.guardar(base)
    history.registrar("Aviso", "1T", 2026, "Zulu SL", "zulu.pdf")
    history.registrar("Aviso", "1T", 2026, "Alfa SL", "alfa.pdf")
    history.registrar("Aviso", "1T", 2026, "Zulu SL", "zulu-2.pdf")

    assert history.clientes_recientes(limite=2) == ["Zulu SL", "Alfa SL"]
    recargados = clients.cargar()
    assert sorted(recargados, key=clave_orden_cliente)[0].nombre == "Alfa SL"
    assert clients.buscar(recargados, "b00000001").nombre == "Zulu SL"
