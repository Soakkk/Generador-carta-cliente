"""Panel de vista previa reutilizable: ajusta la hoja A4 al ancho disponible
y la re-renderiza a la resolucion exacta (nunca escala una imagen ya hecha,
para que el texto salga siempre nitido)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from ..render import A4_W_MM

_MARGEN_PX = 28
_DPI_MIN = 60.0
_DPI_MAX = 220.0

# generador(dpi, info) -> QImage ; `info` es un dict que el generador puede
# rellenar con info["desborda"] = True/False
Generador = Callable[[float, dict], "object"]


class PreviewPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background:#FFFFFF;")
        sombra = QGraphicsDropShadowEffect(self.label)
        sombra.setBlurRadius(28)
        sombra.setOffset(0, 4)
        sombra.setColor(QColor(0, 0, 0, 110))
        self.label.setGraphicsEffect(sombra)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("previewScroll")
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.scroll.setWidget(self.label)
        self.scroll.setStyleSheet(
            "QScrollArea#previewScroll{background:#E8EDF4;border:1px solid #DCE5F0;"
            "border-radius:7px;}"
            "QScrollArea#previewScroll > QWidget > QWidget{background:#E8EDF4;}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._repintar_ultima)
        self._ultimo_generador: Generador | None = None

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._resize_timer.start()

    def _dpi_ajustada(self) -> float:
        ancho_viewport = self.scroll.viewport().width()
        ancho_render = max(ancho_viewport - _MARGEN_PX, 200)
        dpi = ancho_render / (A4_W_MM / 25.4)
        return max(_DPI_MIN, min(dpi, _DPI_MAX))

    def mostrar(self, generador: Generador) -> dict:
        """Renderiza con `generador(dpi, info) -> QImage`. Devuelve `info`."""
        self._ultimo_generador = generador
        info: dict = {}
        try:
            img = generador(self._dpi_ajustada(), info)
            pix = QPixmap.fromImage(img)
            self.label.setText("")
            self.label.setPixmap(pix)
            self.label.setFixedSize(pix.size())
        except Exception as e:
            self.label.setPixmap(QPixmap())
            self.label.setText(f"Error al generar la vista previa:\n{e}")
        return info

    def _repintar_ultima(self) -> None:
        if self._ultimo_generador is not None:
            self.mostrar(self._ultimo_generador)
