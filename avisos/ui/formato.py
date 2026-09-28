"""Editor de formato del documento: fuente, tamano de letra e interlineado,
al estilo Word. Los textos de las plantillas y el calculo de fechas no
cambian; esto solo afecta a la tipografia."""
from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .. import estilo as E
from .. import templates as T
from ..render import fecha_de, render_preview_textos
from .controles import DoubleSpinSinRueda, FuenteSinRueda
from .preview_widget import PreviewPanel


class FormatoDialog(QWidget):
    def __init__(self, parent=None, on_cambio: Callable[[], None] | None = None) -> None:
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Formato del documento")
        self.resize(920, 680)
        self._on_cambio = on_cambio
        self._cargando = True

        izq = QWidget()
        col = QVBoxLayout(izq)
        col.addWidget(QLabel(
            "<b>Formato del documento</b><br>"
            "Los textos de las plantillas y las fechas no cambian: esto solo "
            "afecta a la letra."))

        form = QFormLayout()
        self.cmb_fuente = FuenteSinRueda()
        form.addRow("Fuente:", self.cmb_fuente)

        self.spin_tamano = DoubleSpinSinRueda()
        self.spin_tamano.setRange(8.0, 16.0)
        self.spin_tamano.setSingleStep(0.5)
        self.spin_tamano.setSuffix(" pt")
        form.addRow("Tamaño de letra:", self.spin_tamano)

        self.spin_interlineado = DoubleSpinSinRueda()
        self.spin_interlineado.setRange(100.0, 160.0)
        self.spin_interlineado.setSingleStep(5.0)
        self.spin_interlineado.setSuffix(" %")
        form.addRow("Interlineado:", self.spin_interlineado)

        self.spin_espacio_parrafo = DoubleSpinSinRueda()
        self.spin_espacio_parrafo.setRange(0.0, 16.0)
        self.spin_espacio_parrafo.setSingleStep(1.0)
        self.spin_espacio_parrafo.setSuffix(" pt")
        form.addRow("Espacio entre párrafos:", self.spin_espacio_parrafo)

        col.addLayout(form)
        col.addStretch(1)

        for widget, senal in [
            (self.cmb_fuente, self.cmb_fuente.currentFontChanged),
            (self.spin_tamano, self.spin_tamano.valueChanged),
            (self.spin_interlineado, self.spin_interlineado.valueChanged),
            (self.spin_espacio_parrafo, self.spin_espacio_parrafo.valueChanged),
        ]:
            senal.connect(self._actualizar_preview)

        fila_botones = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_restablecer = QPushButton("Restablecer valores de fábrica")
        self.btn_restablecer.clicked.connect(self._restablecer)
        fila_botones.addWidget(self.btn_guardar)
        fila_botones.addWidget(self.btn_restablecer)
        col.addLayout(fila_botones)

        cerrar = QDialogButtonBox(QDialogButtonBox.Close)
        cerrar.button(QDialogButtonBox.Close).clicked.connect(self.close)
        col.addWidget(cerrar)

        der = QWidget()
        col_der = QVBoxLayout(der)
        col_der.addWidget(QLabel("Vista previa:"))
        self.preview = PreviewPanel()
        col_der.addWidget(self.preview, 1)

        splitter = QSplitter()
        splitter.addWidget(izq)
        splitter.addWidget(der)
        splitter.setSizes([360, 560])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(splitter)

        self._cargar_estilo(E.cargar())
        self._cargando = False
        self._actualizar_preview()

    # ------------------------------------------------------------------
    def _cargar_estilo(self, est: E.Estilo) -> None:
        self.cmb_fuente.setCurrentFont(QFont(est.fuente))
        self.spin_tamano.setValue(est.tamano_cuerpo)
        self.spin_interlineado.setValue(est.interlineado)
        self.spin_espacio_parrafo.setValue(est.espacio_parrafo)

    def _estilo_actual(self) -> E.Estilo:
        return E.Estilo(
            fuente=self.cmb_fuente.currentFont().family(),
            tamano_cuerpo=self.spin_tamano.value(),
            interlineado=self.spin_interlineado.value(),
            espacio_parrafo=self.spin_espacio_parrafo.value(),
        )

    def _contexto_muestra(self) -> tuple[T.Contexto, T.Plantilla]:
        p = T.PLANTILLAS[0]
        ctx = T.Contexto(
            periodo="1T", anio=date.today().year, cliente="Juan Pérez García",
            documentos=p.documentos_def, notas="Ejemplo de una nota adicional.",
        )
        return ctx, p

    def _actualizar_preview(self, *_args) -> None:
        if self._cargando:
            return
        ctx, plantilla = self._contexto_muestra()
        est = self._estilo_actual()
        titulo = T.render_titulo(ctx, plantilla)
        cuerpo_html = T.render_cuerpo(ctx, plantilla)

        def generador(dpi, info):
            return render_preview_textos(titulo, cuerpo_html, dpi=dpi, info=info, est=est,
                                         fecha=fecha_de(ctx))

        self.preview.mostrar(generador)

    def _guardar(self) -> None:
        E.guardar(self._estilo_actual())
        if self._on_cambio:
            self._on_cambio()
        QMessageBox.information(self, "Guardado",
                                 "El formato se ha guardado y se aplicará a los próximos avisos.")

    def _restablecer(self) -> None:
        resp = QMessageBox.question(
            self, "Restablecer",
            "¿Restablecer la fuente, el tamaño y el interlineado a los valores de fábrica?",
            QMessageBox.Yes | QMessageBox.No)
        if resp == QMessageBox.Yes:
            est = E.restablecer()
            self._cargando = True
            self._cargar_estilo(est)
            self._cargando = False
            self._actualizar_preview()
            if self._on_cambio:
                self._on_cambio()
