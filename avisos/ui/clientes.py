"""Dialogo de gestion de la base de datos de clientes."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from .. import clients as C


def guardar_clientes_con_conflictos(parent, clientes: list[C.Cliente]) -> None:
    """Guarda y pide una decisión visible por cada dato compartido distinto."""
    pendientes = C.guardar(clientes)
    decisiones: dict[int, tuple[C.Cliente, dict[str, str]]] = {}
    guardar_local_de_nuevo = False
    for cliente, conflicto in pendientes:
        respuesta = QMessageBox.question(
            parent,
            "Dato distinto en el directorio común",
            f"El campo «{conflicto.campo}» de {cliente.nombre} tiene dos valores:\n\n"
            f"Directorio común: {conflicto.existente}\n"
            f"Cambio actual: {conflicto.entrante}\n\n"
            "Pulsa Sí para usar el cambio actual o No para conservar el valor compartido.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        clave = id(cliente)
        decisiones.setdefault(clave, (replace(cliente), {}))[1][conflicto.campo] = (
            "entrante" if respuesta == QMessageBox.Yes else "existente"
        )
        if respuesta != QMessageBox.Yes:
            setattr(cliente, conflicto.campo, conflicto.existente)
            guardar_local_de_nuevo = True
    for cliente, resolver in decisiones.values():
        C.resolver_conflictos(cliente, resolver)
    if guardar_local_de_nuevo:
        C.guardar(clientes)


def clave_orden_cliente(cliente: C.Cliente | dict) -> tuple[bool, float, str]:
    """Favoritos primero; después uso reciente y nombre estable."""
    if isinstance(cliente, dict):
        favorito = bool(cliente.get("favorito", False))
        ultimo_uso = float(cliente.get("ultimo_uso", 0) or 0)
        nombre = str(cliente.get("nombre", ""))
    else:
        favorito = cliente.favorito
        ultimo_uso = cliente.ultimo_uso
        nombre = cliente.nombre
    return (not favorito, -ultimo_uso, nombre.casefold())


class EditorClienteDialog(QDialog):
    """Formulario para anadir o editar un unico cliente."""

    def __init__(self, parent=None, cliente: C.Cliente | None = None) -> None:
        super().__init__(parent)
        self._cliente_original = cliente
        self.setWindowTitle("Editar cliente" if cliente else "Nuevo cliente")
        self.setMinimumWidth(360)

        form = QFormLayout()
        self.txt_nombre = QLineEdit(cliente.nombre if cliente else "")
        self.txt_nif = QLineEdit(cliente.nif if cliente else "")
        self.txt_direccion = QLineEdit(cliente.direccion if cliente else "")
        self.txt_iban = QLineEdit(cliente.iban if cliente else "")
        self.txt_telefono = QLineEdit(cliente.telefono if cliente else "")
        self.txt_email = QLineEdit(cliente.email if cliente else "")
        self.chk_favorito = QCheckBox("Mostrar antes que los demás clientes")
        self.chk_favorito.setChecked(cliente.favorito if cliente else False)
        form.addRow("Nombre:", self.txt_nombre)
        form.addRow("NIF:", self.txt_nif)
        form.addRow("Dirección:", self.txt_direccion)
        form.addRow("IBAN:", self.txt_iban)
        form.addRow("Teléfono:", self.txt_telefono)
        form.addRow("Email:", self.txt_email)
        form.addRow("Favorito:", self.chk_favorito)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botones)

    def _aceptar(self) -> None:
        if not self.txt_nombre.text().strip():
            QMessageBox.warning(self, "Falta el nombre", "El nombre del cliente es obligatorio.")
            return
        self.accept()

    def cliente(self) -> C.Cliente:
        return C.Cliente(
            nombre=self.txt_nombre.text().strip(),
            nif=self.txt_nif.text().strip(),
            direccion=self.txt_direccion.text().strip(),
            iban=self.txt_iban.text().strip(),
            telefono=self.txt_telefono.text().strip(),
            email=self.txt_email.text().strip(),
            favorito=self.chk_favorito.isChecked(),
            ultimo_uso=self._cliente_original.ultimo_uso if self._cliente_original else 0.0,
        )


class ClientesDialog(QDialog):
    """Tabla con alta / edicion / baja de clientes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Clientes")
        self.resize(620, 440)
        self._clientes = C.cargar()

        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar por nombre, NIF, teléfono o email…")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.textChanged.connect(self._refrescar_tabla)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Favorito", "Nombre", "NIF", "Teléfono", "Email"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.doubleClicked.connect(self._editar)

        btn_anadir = QPushButton("Añadir…")
        btn_anadir.clicked.connect(self._anadir)
        btn_editar = QPushButton("Editar…")
        btn_editar.clicked.connect(self._editar)
        btn_eliminar = QPushButton("Eliminar")
        btn_eliminar.clicked.connect(self._eliminar)
        fila_botones = QHBoxLayout()
        fila_botones.addWidget(btn_anadir)
        fila_botones.addWidget(btn_editar)
        fila_botones.addWidget(btn_eliminar)
        fila_botones.addStretch(1)

        cerrar = QDialogButtonBox(QDialogButtonBox.Close)
        cerrar.rejected.connect(self.reject)
        cerrar.accepted.connect(self.accept)
        cerrar.button(QDialogButtonBox.Close).clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.txt_buscar)
        layout.addWidget(self.tabla)
        layout.addLayout(fila_botones)
        layout.addWidget(cerrar)

        self._refrescar_tabla()

    # ------------------------------------------------------------------
    def _refrescar_tabla(self, *_args) -> None:
        self._clientes.sort(key=clave_orden_cliente)
        filtro = self.txt_buscar.text().strip().lower()
        self._visibles = [c for c in self._clientes if filtro in " ".join((
            c.nombre, c.nif, c.telefono, c.email)).lower()] if filtro else list(self._clientes)
        self.tabla.setRowCount(len(self._visibles))
        for fila, c in enumerate(self._visibles):
            for col, valor in enumerate([
                "Sí" if c.favorito else "", c.nombre, c.nif, c.telefono, c.email
            ]):
                self.tabla.setItem(fila, col, QTableWidgetItem(valor))

    def _fila_seleccionada(self) -> int:
        filas = self.tabla.selectionModel().selectedRows()
        return filas[0].row() if filas else -1

    def _anadir(self) -> None:
        dlg = EditorClienteDialog(self)
        if dlg.exec() == QDialog.Accepted:
            nuevo = dlg.cliente()
            if C.buscar(self._clientes, nuevo.nombre):
                QMessageBox.warning(
                    self, "Cliente ya existe",
                    f"Ya hay un cliente llamado «{nuevo.nombre}».")
                return
            self._clientes = C.upsert(self._clientes, nuevo)
            guardar_clientes_con_conflictos(self, self._clientes)
            self._refrescar_tabla()

    def _editar(self) -> None:
        fila = self._fila_seleccionada()
        if fila < 0:
            return
        original = self._visibles[fila]
        dlg = EditorClienteDialog(self, original)
        if dlg.exec() == QDialog.Accepted:
            self._clientes = C.upsert(self._clientes, dlg.cliente(), original.nombre)
            guardar_clientes_con_conflictos(self, self._clientes)
            self._refrescar_tabla()

    def _eliminar(self) -> None:
        fila = self._fila_seleccionada()
        if fila < 0:
            return
        nombre = self._visibles[fila].nombre
        resp = QMessageBox.question(
            self, "Eliminar cliente", f"¿Eliminar a «{nombre}»?",
            QMessageBox.Yes | QMessageBox.No)
        if resp == QMessageBox.Yes:
            self._clientes = C.eliminar(self._clientes, nombre)
            guardar_clientes_con_conflictos(self, self._clientes)
            self._refrescar_tabla()
