"""Editor de plantillas: permite cambiar los textos de los avisos sin tocar codigo."""
from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .. import templates as T
from ..render import fecha_de, render_preview_textos
from .controles import ComboSinRueda
from .preview_widget import PreviewPanel


class PlantillaEditorDialog(QWidget):
    """Ventana (no modal) para editar el titulo/cuerpo de cada plantilla."""

    def __init__(self, parent=None, on_cambio: Callable[[], None] | None = None) -> None:
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Editar plantillas")
        self.resize(1080, 720)
        self._cargando = False
        self._on_cambio = on_cambio

        # ---- Columna izquierda: edicion ----
        izq = QWidget()
        col = QVBoxLayout(izq)

        self.cmb_plantilla = ComboSinRueda()
        for p in T.PLANTILLAS:
            self.cmb_plantilla.addItem(p.nombre, p.id)
            self.cmb_plantilla.setItemData(
                self.cmb_plantilla.count() - 1, f"{p.grupo}\n{p.nombre}", Qt.ToolTipRole)
        ancho = max((self.cmb_plantilla.fontMetrics().horizontalAdvance(
            self.cmb_plantilla.itemText(i)) for i in range(self.cmb_plantilla.count())), default=0)
        self.cmb_plantilla.view().setMinimumWidth(min(ancho + 56, 620))
        self.cmb_plantilla.currentIndexChanged.connect(self._cargar_plantilla)
        col.addWidget(QLabel("Plantilla:"))
        col.addWidget(self.cmb_plantilla)
        self.lbl_grupo = QLabel("")
        self.lbl_grupo.setObjectName("textoSuave")
        col.addWidget(self.lbl_grupo)

        self.lbl_estado = QLabel("")
        col.addWidget(self.lbl_estado)

        col.addWidget(QLabel("Título:"))
        self.txt_titulo = QLineEdit()
        self.txt_titulo.textChanged.connect(self._on_editado)
        col.addWidget(self.txt_titulo)

        col.addWidget(QLabel("Cuerpo del aviso:"))
        self.txt_cuerpo = QPlainTextEdit()
        mono = QFont("Consolas")
        mono.setPointSize(10)
        self.txt_cuerpo.setFont(mono)
        self.txt_cuerpo.textChanged.connect(self._on_editado)
        col.addWidget(self.txt_cuerpo, 1)

        leyenda = QLabel(
            "<b>Cómo escribir el texto:</b> deja una línea en blanco entre párrafos. "
            "Escribe *así* para poner algo en <b>negrita</b>.<br>"
            "<b>Placeholders disponibles:</b> " +
            " · ".join(f"<code>{k}</code>" for k, _ in T.PLACEHOLDERS_DISPONIBLES) +
            "<br><i>{documentos}, {notas}, {tabla_plazos} y {felicitacion_navidad} "
            "deben ir solos en su propio párrafo; si no aplican, desaparecen solos.</i>")
        leyenda.setWordWrap(True)
        leyenda.setStyleSheet("color:#555;")
        col.addWidget(leyenda)

        fila_botones = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_restablecer = QPushButton("Restablecer al texto de fábrica")
        self.btn_restablecer.clicked.connect(self._restablecer)
        fila_botones.addWidget(self.btn_guardar)
        fila_botones.addWidget(self.btn_restablecer)
        col.addLayout(fila_botones)

        cerrar = QDialogButtonBox(QDialogButtonBox.Close)
        cerrar.button(QDialogButtonBox.Close).clicked.connect(self.close)
        col.addWidget(cerrar)

        # ---- Columna derecha: vista previa ----
        der = QWidget()
        col_der = QVBoxLayout(der)
        col_der.addWidget(QLabel("Vista previa (con datos de ejemplo):"))
        self.preview = PreviewPanel()
        col_der.addWidget(self.preview, 1)

        splitter = QSplitter()
        splitter.addWidget(izq)
        splitter.addWidget(der)
        splitter.setSizes([460, 620])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(splitter)

        self._cargar_plantilla()

    # ------------------------------------------------------------------
    def _plantilla_actual(self) -> T.Plantilla:
        return T.por_id(self.cmb_plantilla.currentData())

    def _contexto_muestra(self, plantilla: T.Plantilla) -> T.Contexto:
        return T.Contexto(
            periodo="1T",
            anio=date.today().year,
            cliente="Juan Pérez García",
            fecha_limite=None,
            documentos=plantilla.documentos_def,
            navidad=plantilla.usa_navidad,
            notas="Ejemplo de una nota adicional.",
        )

    def _cargar_plantilla(self) -> None:
        self._cargando = True
        p = self._plantilla_actual()
        self.lbl_grupo.setText(p.grupo)
        self.txt_titulo.setText(T.titulo_tpl_activo(p))
        self.txt_cuerpo.setPlainText(T.cuerpo_tpl_activo(p))
        self._actualizar_estado(p)
        self._cargando = False
        self._actualizar_preview()

    def _actualizar_estado(self, plantilla: T.Plantilla) -> None:
        if T.tiene_override(plantilla.id):
            self.lbl_estado.setText("✓ Usando texto personalizado")
            self.lbl_estado.setStyleSheet("color:#2E4A3C; font-weight:bold;")
        else:
            self.lbl_estado.setText("Usando el texto de fábrica")
            self.lbl_estado.setStyleSheet("color:#777;")

    def _on_editado(self) -> None:
        if not self._cargando:
            self._actualizar_preview()

    def _actualizar_preview(self) -> None:
        plantilla = self._plantilla_actual()
        ctx = self._contexto_muestra(plantilla)
        titulo_texto = self.txt_titulo.text()
        cuerpo_texto = self.txt_cuerpo.toPlainText()

        def generador(dpi, info):
            titulo = T.render_titulo_texto(ctx, titulo_texto)
            cuerpo_html = T.render_cuerpo_texto(ctx, cuerpo_texto)
            return render_preview_textos(titulo, cuerpo_html, dpi=dpi, info=info,
                                         fecha=fecha_de(ctx))

        self.preview.mostrar(generador)

    def _guardar(self) -> None:
        p = self._plantilla_actual()
        if not self.txt_titulo.text().strip() or not self.txt_cuerpo.toPlainText().strip():
            QMessageBox.warning(self, "Texto vacío",
                                 "El título y el cuerpo no pueden quedar vacíos.")
            return
        T.guardar_override(p.id, self.txt_titulo.text(), self.txt_cuerpo.toPlainText())
        self._actualizar_estado(p)
        if self._on_cambio:
            self._on_cambio()
        QMessageBox.information(self, "Guardado", "Los cambios se han guardado.")

    def _restablecer(self) -> None:
        p = self._plantilla_actual()
        resp = QMessageBox.question(
            self, "Restablecer",
            f"¿Restablecer «{p.nombre}» al texto de fábrica?\n"
            "Se perderán los cambios personalizados de esta plantilla.",
            QMessageBox.Yes | QMessageBox.No)
        if resp == QMessageBox.Yes:
            T.restablecer_override(p.id)
            self._cargar_plantilla()
            if self._on_cambio:
                self._on_cambio()
