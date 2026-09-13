"""Generar el mismo aviso (misma plantilla y mismos datos) para varios
clientes de golpe: una copia individual del PDF por cada nombre elegido.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHeaderView, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .. import clients as C
from .. import history as H
from .. import templates as T
from ..batch import BatchItem, BatchState, borrar_lote, cargar_lote, guardar_lote
from ..render import render_pdf_plantilla_texto
from ..suite_storage import normalizar_nif
from ..templates import Contexto, Plantilla
from ..util import nombre_archivo, ruta_sin_colision


class LoteDialog(QDialog):
    def __init__(self, parent, ctx_base: Contexto, plantilla: Plantilla,
                 carpeta_inicial: str, documento_tpl: tuple[str, str] | None = None,
                 extras_etiquetas: list[str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generar para varios clientes")
        self.resize(520, 560)
        self._ctx_base = ctx_base
        self._plantilla = plantilla
        self._carpeta = carpeta_inicial
        self._documento_tpl = documento_tpl or (
            T.titulo_tpl_activo(plantilla), T.cuerpo_tpl_activo(plantilla))
        self._extras_etiquetas = list(extras_etiquetas or [])
        self._ejecutando = False
        self._cancelar_solicitado = False
        self._lote = self._cargar_lote_compatible()

        info = QLabel(
            f"Se generará un PDF individual por cada cliente marcado, usando:\n"
            f"«{plantilla.nombre}» — {self._ctx_base.periodo_largo} de {self._ctx_base.anio}")
        info.setWordWrap(True)

        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar cliente por nombre o NIF…")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.textChanged.connect(self._filtrar)

        self.lista = QListWidget()
        for c in sorted(C.cargar(), key=lambda x: x.nombre.lower()):
            detalle = f" — {c.nif}" if c.nif else ""
            item = QListWidgetItem(c.nombre + detalle)
            item.setData(Qt.UserRole, c.nombre)
            item.setData(Qt.UserRole + 1, f"{c.nombre} {c.nif}".lower())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.lista.addItem(item)

        fila_marcar = QHBoxLayout()
        btn_todos = QPushButton("Marcar todos")
        btn_todos.clicked.connect(lambda: self._marcar_todos(Qt.Checked))
        btn_ninguno = QPushButton("Desmarcar todos")
        btn_ninguno.clicked.connect(lambda: self._marcar_todos(Qt.Unchecked))
        fila_marcar.addWidget(btn_todos)
        fila_marcar.addWidget(btn_ninguno)
        fila_marcar.addStretch(1)

        self.txt_sueltos = QPlainTextEdit()
        self.txt_sueltos.setPlaceholderText(
            "Nombres sueltos que no estén en la base de datos (uno por línea, opcional)")
        self.txt_sueltos.setMaximumHeight(80)

        fila_carpeta = QHBoxLayout()
        self.lbl_carpeta = QLabel(self._carpeta)
        self.lbl_carpeta.setWordWrap(True)
        btn_carpeta = QPushButton("Elegir carpeta…")
        btn_carpeta.clicked.connect(self._elegir_carpeta)
        fila_carpeta.addWidget(QLabel("Guardar en:"))
        fila_carpeta.addWidget(self.lbl_carpeta, 1)
        fila_carpeta.addWidget(btn_carpeta)

        self.tabla_cola = QTableWidget(0, 3)
        self.tabla_cola.setHorizontalHeaderLabels(["Cliente", "Estado", "Salida o recuperación"])
        self.tabla_cola.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabla_cola.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabla_cola.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_cola.setVisible(bool(self._lote and self._lote.items))

        self.progreso = QProgressBar()
        self.progreso.setTextVisible(True)
        self.progreso.setVisible(bool(self._lote and self._lote.items))

        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setWordWrap(True)
        self.lbl_resumen.setVisible(False)

        fila_resumen = QHBoxLayout()
        self.btn_abrir_carpeta = QPushButton("Abrir carpeta")
        self.btn_abrir_carpeta.clicked.connect(self._abrir_carpeta)
        self.btn_abrir_carpeta.setVisible(False)
        self.btn_reintentar = QPushButton("Reintentar fallidos")
        self.btn_reintentar.clicked.connect(self._reintentar_fallidos)
        self.btn_reintentar.setVisible(False)
        self.btn_terminar = QPushButton("Terminar")
        self.btn_terminar.clicked.connect(self._terminar)
        self.btn_terminar.setVisible(False)
        fila_resumen.addWidget(self.btn_abrir_carpeta)
        fila_resumen.addWidget(self.btn_reintentar)
        fila_resumen.addStretch(1)
        fila_resumen.addWidget(self.btn_terminar)

        fila_botones = QHBoxLayout()
        self.btn_generar = QPushButton("Generar avisos")
        self.btn_generar.setMinimumHeight(36)
        self.btn_generar.clicked.connect(self._generar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self._cancelar)
        fila_botones.addWidget(self.btn_generar)
        fila_botones.addWidget(self.btn_cancelar)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(QLabel("Clientes de la base de datos:"))
        layout.addWidget(self.txt_buscar)
        layout.addWidget(self.lista, 1)
        layout.addLayout(fila_marcar)
        layout.addWidget(self.txt_sueltos)
        layout.addLayout(fila_carpeta)
        layout.addWidget(self.tabla_cola)
        layout.addWidget(self.progreso)
        layout.addWidget(self.lbl_resumen)
        layout.addLayout(fila_resumen)
        layout.addLayout(fila_botones)
        if self._lote:
            self._carpeta = self._lote.carpeta or self._carpeta
            self.lbl_carpeta.setText(self._carpeta)
            self._actualizar_cola()

    # ------------------------------------------------------------------
    def carpeta_usada(self) -> str:
        return self._carpeta

    def _marcar_todos(self, estado) -> None:
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if not item.isHidden():
                item.setCheckState(estado)

    def _filtrar(self, texto: str) -> None:
        filtro = texto.strip().lower()
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            item.setHidden(bool(filtro and filtro not in item.data(Qt.UserRole + 1)))

    def _elegir_carpeta(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(self, "Elegir carpeta destino", self._carpeta)
        if carpeta:
            self._carpeta = carpeta
            self.lbl_carpeta.setText(carpeta)

    def _nombres_elegidos(self) -> list[str]:
        nombres = [self.lista.item(i).data(Qt.UserRole) for i in range(self.lista.count())
                   if self.lista.item(i).checkState() == Qt.Checked]
        sueltos = [ln.strip() for ln in self.txt_sueltos.toPlainText().splitlines() if ln.strip()]
        resultado: list[str] = []
        vistos: set[str] = set()
        for nombre in nombres + sueltos:
            clave = nombre.strip().lower()
            if clave and clave not in vistos:
                vistos.add(clave)
                resultado.append(nombre.strip())
        return resultado

    def _configuracion_serie(self) -> dict:
        return {
            "plantilla_id": self._plantilla.id,
            "periodo": self._ctx_base.periodo,
            "anio": self._ctx_base.anio,
            "documentos": list(self._ctx_base.documentos),
            "documentos_extra": [
                [intro, list(lineas)] for intro, lineas in self._ctx_base.documentos_extra
            ],
            "fecha_limite": (
                self._ctx_base.fecha_limite.isoformat() if self._ctx_base.fecha_limite else ""
            ),
            "navidad": self._ctx_base.navidad,
            "notas": self._ctx_base.notas,
            "extras": list(self._extras_etiquetas),
            "titulo_tpl": self._documento_tpl[0],
            "cuerpo_tpl": self._documento_tpl[1],
        }

    def _cargar_lote_compatible(self) -> BatchState | None:
        lote = cargar_lote()
        if lote is None:
            return None
        if lote.configuracion.get("plantilla_id") != self._plantilla.id:
            return None
        cfg = lote.configuracion
        try:
            periodo = str(cfg["periodo"])
            anio = int(cfg["anio"])
            documentos = list(cfg["documentos"])
            titulo = str(cfg["titulo_tpl"])
            cuerpo = str(cfg["cuerpo_tpl"])
            extras = list(cfg.get("extras", []))
            documentos_extra = [
                (str(intro), [str(linea) for linea in lineas])
                for intro, lineas in cfg.get("documentos_extra", [])
            ]
            fecha_txt = str(cfg.get("fecha_limite", ""))
            fecha_limite = date.fromisoformat(fecha_txt) if fecha_txt else None
            if periodo not in T.PERIODOS or not all(isinstance(d, str) for d in documentos):
                return None
        except (KeyError, TypeError, ValueError):
            return None
        self._ctx_base = replace(
            self._ctx_base,
            periodo=periodo,
            anio=anio,
            documentos=documentos,
            documentos_extra=documentos_extra,
            fecha_limite=fecha_limite,
            navidad=bool(cfg.get("navidad", False)),
            notas=str(cfg.get("notas", "")),
        )
        self._documento_tpl = (titulo, cuerpo)
        self._extras_etiquetas = [str(extra) for extra in extras]
        return lote

    def _iniciar_lote(self, nombres: list[str]) -> None:
        items: list[BatchItem] = []
        clientes = C.cargar()
        for indice, nombre in enumerate(nombres, start=1):
            cliente = C.buscar(clientes, nombre)
            nif = normalizar_nif(cliente.nif if cliente else "")
            items.append(BatchItem(
                id=str(indice), cliente_nif=nif, nombre=nombre,
            ))
        self._lote = BatchState(
            items=items,
            carpeta=self._carpeta,
            modo_salida="pdf",
            configuracion=self._configuracion_serie(),
        )
        guardar_lote(self._lote)
        self._actualizar_cola()

    def _estado_visible(self, estado: str) -> str:
        return {
            "pendiente": "Pendiente",
            "generando": "Generando",
            "completado": "Completado",
            "fallido": "Fallido",
        }.get(estado, estado)

    def _actualizar_cola(self) -> None:
        if self._lote is None:
            return
        self.tabla_cola.setVisible(True)
        self.progreso.setVisible(True)
        self.tabla_cola.setRowCount(len(self._lote.items))
        terminados = 0
        fallidos = 0
        for fila, item in enumerate(self._lote.items):
            if item.estado in ("completado", "fallido"):
                terminados += 1
            if item.estado == "fallido":
                fallidos += 1
            detalle = item.salida
            if item.error:
                detalle = f"{item.error}. Corrige el problema y pulsa Reintentar fallidos."
            for columna, valor in enumerate((
                item.nombre or item.cliente_nif,
                self._estado_visible(item.estado),
                detalle,
            )):
                self.tabla_cola.setItem(fila, columna, QTableWidgetItem(valor))
        self.progreso.setRange(0, len(self._lote.items))
        self.progreso.setValue(terminados)
        completados = sum(i.estado == "completado" for i in self._lote.items)
        self.lbl_resumen.setText(
            f"{completados} completados · {fallidos} fallidos · "
            f"{len(self._lote.items) - terminados} pendientes"
        )
        mostrar_resumen = terminados == len(self._lote.items) or self._lote.cancelado
        self.lbl_resumen.setVisible(mostrar_resumen)
        self.btn_abrir_carpeta.setVisible(mostrar_resumen and completados > 0)
        self.btn_reintentar.setVisible(mostrar_resumen and fallidos > 0)
        self.btn_terminar.setVisible(mostrar_resumen)
        self.btn_generar.setText("Reanudar pendientes" if self._lote.cancelado else "Generar avisos")

    def _procesar_lote(self) -> None:
        if self._lote is None:
            return
        self._lote.reanudar()
        self._ejecutando = True
        self._cancelar_solicitado = False
        self.btn_generar.setEnabled(False)
        try:
            while not self._cancelar_solicitado:
                item = self._lote.siguiente()
                if item is None:
                    break
                guardar_lote(self._lote)
                self._actualizar_cola()
                QApplication.processEvents()

                cliente = C.buscar(C.cargar(), item.cliente_nif or item.nombre)
                nif = cliente.nif if cliente else item.cliente_nif
                ctx = replace(self._ctx_base, cliente=item.nombre, nif=nif)
                try:
                    if item.pdf_generado and item.salida and Path(item.salida).exists():
                        ruta = Path(item.salida)
                    else:
                        ruta = (
                            Path(item.salida) if item.salida else ruta_sin_colision(
                                Path(self._lote.carpeta), nombre_archivo(self._plantilla, ctx)
                            )
                        )
                        render_pdf_plantilla_texto(ctx, *self._documento_tpl, ruta)
                        self._lote.marcar_pdf(item.id, str(ruta))
                        guardar_lote(self._lote)
                    if not item.historial_registrado:
                        H.registrar(
                            self._plantilla.nombre, ctx.periodo_corto, ctx.anio,
                            item.nombre, str(ruta), plantilla_id=self._plantilla.id,
                            documentos=ctx.documentos, extras=self._extras_etiquetas,
                            navidad=ctx.navidad, notas=ctx.notas,
                            titulo_tpl=self._documento_tpl[0], cuerpo_tpl=self._documento_tpl[1],
                        )
                        self._lote.marcar_historial(item.id)
                        guardar_lote(self._lote)
                    C.asegurar_cliente(item.nombre, nif)
                    C.registrar_uso(item.nombre)
                    self._lote.marcar_ok(item.id, str(ruta))
                except Exception as exc:
                    self._lote.marcar_error(item.id, str(exc))
                guardar_lote(self._lote)
                self._actualizar_cola()
                QApplication.processEvents()
            if self._cancelar_solicitado:
                self._lote.cancelar()
                guardar_lote(self._lote)
        finally:
            self._ejecutando = False
            self.btn_generar.setEnabled(True)
            self.btn_cancelar.setText("Cancelar")
            self.btn_cancelar.setEnabled(True)
            self._actualizar_cola()

    def _generar(self) -> None:
        pendientes_previos = bool(
            self._lote and any(i.estado == "pendiente" for i in self._lote.items)
        )
        if not pendientes_previos:
            nombres = self._nombres_elegidos()
            if not nombres:
                QMessageBox.warning(self, "Sin clientes",
                                     "Marca al menos un cliente o escribe algún nombre suelto.")
                return
        carpeta = Path(self._carpeta)
        if not carpeta.exists():
            QMessageBox.warning(self, "Carpeta no válida", "Elige una carpeta de destino válida.")
            return
        if not pendientes_previos:
            self._iniciar_lote(nombres)
        else:
            self._lote.carpeta = self._carpeta
        self._procesar_lote()

    def _cancelar(self) -> None:
        if self._ejecutando:
            self._cancelar_solicitado = True
            self.btn_cancelar.setText("Cancelando…")
            self.btn_cancelar.setEnabled(False)
            return
        if self._lote and any(i.estado == "pendiente" for i in self._lote.items):
            self._lote.cancelar()
            guardar_lote(self._lote)
        self.reject()

    def _reintentar_fallidos(self) -> None:
        if self._lote is None:
            return
        self._lote.reintentar_fallidos()
        guardar_lote(self._lote)
        self._procesar_lote()

    def _abrir_carpeta(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._carpeta))))

    def _terminar(self) -> None:
        borrar_lote()
        self.accept()
