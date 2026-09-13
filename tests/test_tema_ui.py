from __future__ import annotations

import pytest
from PySide6.QtGui import QIcon, QImage, QKeySequence
from PySide6.QtWidgets import QApplication

from avisos import tema_ui
from avisos import templates
from avisos import config
from avisos.app import MainWindow


TOKENS = {
    "PAGE": "#F5F8FC",
    "CARD": "#FFFFFF",
    "INK": "#24384D",
    "MUTED": "#5D7084",
    "BORDER": "#DCE5F0",
    "ACCENT": "#326FA6",
    "SUCCESS": "#19724E",
    "WARNING": "#86500A",
    "DANGER": "#B43737",
}


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    tema_ui.aplicar_tema(app)
    yield app


@pytest.fixture
def win(monkeypatch, tmp_path, qapp):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(templates, "_overrides_cache", {})
    ventana = MainWindow()
    ventana._comprobacion_inicial_hecha = True
    ventana.show()
    qapp.processEvents()
    yield ventana
    ventana.close()
    ventana.deleteLater()
    qapp.processEvents()


def test_tema_usa_tokens_exactos_y_tipografia_de_la_suite():
    """Desviar un token o la familia rompería la identidad entre aplicaciones."""
    for nombre, valor in TOKENS.items():
        assert getattr(tema_ui, nombre) == valor
        assert valor in tema_ui.QSS
    assert '"Segoe UI Variable", "Segoe UI"' in tema_ui.QSS
    assert "#0B3159" not in tema_ui.QSS


def test_copiar_es_la_unica_accion_primaria_y_tiene_atajo(win):
    """Promover guardados competiría con la acción diaria de copiar texto."""
    assert win.btn_copiar.objectName() == "primario"
    assert win.btn_pdf.objectName() != "primario"
    assert win.btn_siguiente.objectName() != "primario"
    assert win.btn_guardar_abrir.objectName() != "primario"
    assert win.btn_copiar.shortcut() == QKeySequence("Ctrl+Return")


def test_modo_compacto_evitar_desbordes_sin_ocultar_acciones_clave(win):
    """Una barra desbordada hace inaccesibles acciones en portátiles."""
    win._aplicar_modo_compacto(1024)
    assert win._modo_compacto is True
    assert not win.btn_carpeta.isVisible()
    assert all(not boton.isVisible() for boton in win._acciones_cabecera)
    assert win.btn_pdf.text() == "Guardar PDF"
    assert win.btn_siguiente.text() == "Guardar y siguiente"
    assert win.btn_guardar_def.text() == "Guardar base"
    assert win.btn_restaurar.text() == "Restaurar plantilla"
    assert win.btn_copiar.isVisible()

    win._aplicar_modo_compacto(1440)
    assert win._modo_compacto is False
    assert win.btn_carpeta.isVisible()
    assert all(boton.isVisible() for boton in win._acciones_cabecera)
    assert win.btn_guardar_def.text() == "Guardar como predeterminado"
    assert win.btn_restaurar.text() == "Restaurar texto de la plantilla"


def test_paneles_emplean_la_jerarquia_visual_compartida(win):
    """Volver a dos tarjetas equivalentes perdería la jerarquía formulario/documento."""
    assert win.panel_formulario.objectName() == "panelFormulario"
    assert win.panel_documento.objectName() == "panelDocumento"
    assert win.cabecera.maximumHeight() <= 58


def test_estados_qt_incluyen_foco_disabled_error_y_scrollbars():
    """Sin estados visibles, teclado, errores y listas largas quedan ambiguos."""
    for selector in (
        "QPushButton:focus",
        "QPushButton:disabled",
        "QLineEdit:focus",
        "QLabel#estadoError",
        "QScrollBar:vertical",
        "QTableWidget",
    ):
        assert selector in tema_ui.QSS


def test_icono_comparte_rombo_azul_carta_blanca_y_acento_dorado(qapp):
    """Recuperar el sobre azul marino rompería la identificación de la suite."""
    imagen = QImage(str(config.asset("app-icon.png"))).convertToFormat(
        QImage.Format_RGBA8888)
    assert (imagen.width(), imagen.height()) == (512, 512)
    assert imagen.pixelColor(0, 0).alpha() == 0
    colores = {
        imagen.pixelColor(x, y).name().upper()
        for y in range(imagen.height())
        for x in range(imagen.width())
        if imagen.pixelColor(x, y).alpha() == 255
    }
    assert {"#326FA6", "#FFFFFF", "#F2B52D"} <= colores

    tamanos = {(s.width(), s.height()) for s in QIcon(str(config.asset("app.ico"))).availableSizes()}
    assert tamanos == {
        (16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)
    }
