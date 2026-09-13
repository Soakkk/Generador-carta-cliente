"""Ventana principal del generador de avisos."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QByteArray, QDate, QSize, QStringListModel, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap, QTextListFormat
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSplitter,
    QStackedWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from . import __version__
from . import clients as C
from . import config
from . import estilo as E
from . import extras as X
from . import history as H
from . import render as R
from . import templates as T
from . import updater as U
from .draft import guardar_borrador, leer_borrador
from .log import logger
from .ui.actualizaciones import comprobar_actualizaciones, iniciar_instalador
from .ui.clientes import ClientesDialog, EditorClienteDialog, guardar_clientes_con_conflictos
from .ui.clientes import clave_orden_cliente
from .ui.controles import ComboSinRueda, FechaSinRueda, SpinSinRueda
from .ui.extras import ExtrasDialog
from .ui.formato import FormatoDialog
from .ui.historial import HistorialDialog
from .ui.lote import LoteDialog
from .ui.plantillas import PlantillaEditorDialog
from .ui.preview_widget import PreviewPanel
from .util import nombre_archivo, ruta_sin_colision


def _ajustar_desplegable(combo: QComboBox) -> None:
    """Da al popup una anchura util sin permitir que invada toda la pantalla."""
    fm = combo.fontMetrics()
    ancho = max((fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())), default=0)
    combo.view().setMinimumWidth(min(max(ancho + 56, combo.minimumSizeHint().width()), 620))
    combo.view().setSpacing(2)
    for i in range(combo.count()):
        combo.setItemData(i, combo.itemText(i), Qt.ToolTipRole)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} — v{__version__}")
        self.resize(1360, 880)
        self.setMinimumSize(980, 700)
        icon = config.asset("app-icon.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))

        self._docs_tocados = False       # el usuario edito la lista de documentos
        self._editor_dirty = False       # el usuario edito el texto del aviso a mano
        self._datos_pendientes = False   # cambio el formulario tras editar a mano
        self._cargando_editor = False    # evita marcar dirty al cargar por codigo
        self._editor_plantillas: PlantillaEditorDialog | None = None
        self._editor_formato: FormatoDialog | None = None
        self._comprobacion_inicial_hecha = False
        self._estado_actualizacion = U.ESTADO_INACTIVA
        self._ruta_update_lista: str | None = None
        self._instalar_al_cerrar = False
        self._restaurando_borrador = False
        self._undo_cliente: dict | None = None
        self._undo_documento: tuple[int, str] | None = None
        self._extra_buttons: dict[str, QToolButton] = {}
        self._carpeta_destino = str(Path.home() / "Desktop")

        self._construir_menu()
        self._construir_ui()
        self._timer_borrador = QTimer(self)
        self._timer_borrador.setSingleShot(True)
        self._timer_borrador.setInterval(300)
        self._timer_borrador.timeout.connect(self._guardar_borrador_ahora)
        self._timer_actualizaciones = QTimer(self)
        self._timer_actualizaciones.setInterval(6 * 60 * 60 * 1000)
        self._timer_actualizaciones.timeout.connect(self._comprobar_actualizacion_periodica)
        self._timer_actualizaciones.start()
        self._aplicar_periodo_sugerido()
        self._cargar_ajustes()
        self._refrescar_completer_clientes()
        self._refrescar_lista_extras()
        self._on_plantilla_cambia(forzar_docs=True)
        self._regenerar_editor()
        borrador = leer_borrador()
        if borrador:
            self._restaurar_borrador(borrador)

    # ------------------------------------------------------------------ menu
    def _construir_menu(self) -> None:
        menu = self.menuBar().addMenu("Herramientas")
        menu.addAction("Clientes…", self._abrir_clientes)
        menu.addAction("Generar para varios clientes…", self._abrir_lote)
        menu.addAction("Historial de avisos…", self._abrir_historial)
        accion_deshacer = menu.addAction("Deshacer cambio de cliente", self._deshacer_cambio_cliente)
        accion_deshacer.setShortcut("Ctrl+Shift+Z")
        accion_deshacer_doc = menu.addAction(
            "Deshacer eliminación de documento", self._deshacer_eliminacion_documento
        )
        accion_deshacer_doc.setShortcut("Ctrl+Alt+Z")
        menu.addSeparator()
        menu.addAction("Editar plantillas…", self._abrir_editor_plantillas)
        menu.addAction("Formato del documento…", self._abrir_formato)
        menu.addAction("Documentación opcional…", self._abrir_extras)
        menu.addSeparator()
        menu.addAction("Elegir carpeta de PDF…", self._elegir_carpeta_destino)
        menu.addAction("Abrir carpeta de datos…", self._abrir_carpeta_datos)

        ayuda = self.menuBar().addMenu("Ayuda")
        ayuda.addAction("Buscar actualizaciones…", self._buscar_actualizaciones_manual)
        ayuda.addAction("Acerca de…", self._acerca_de)

    # ------------------------------------------------------------------ UI
    def _construir_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.cabecera = QFrame()
        self.cabecera.setObjectName("cabecera")
        self.cabecera.setFixedHeight(56)
        lc = QHBoxLayout(self.cabecera)
        lc.setContentsMargins(18, 8, 18, 8)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(config.asset("app-icon.png"))).scaled(
            36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setFixedSize(40, 40)
        lc.addWidget(logo)
        marca = QVBoxLayout()
        titulo = QLabel("Avisos Asesoría E. Marín")
        titulo.setObjectName("marca")
        subtitulo = QLabel("Documentación trimestral y Renta")
        subtitulo.setObjectName("marcaSubtitulo")
        marca.addWidget(titulo)
        marca.addWidget(subtitulo)
        lc.addLayout(marca)
        lc.addStretch()
        self._acciones_cabecera = []
        for texto, slot in (("Clientes", self._abrir_clientes),
                            ("Historial", self._abrir_historial),
                            ("Varios clientes", self._abrir_lote)):
            boton = QPushButton(texto)
            boton.setObjectName("cabeceraAccion")
            boton.clicked.connect(slot)
            lc.addWidget(boton)
            self._acciones_cabecera.append(boton)
        raiz.addWidget(self.cabecera)

        contenido = QWidget()
        cuerpo = QVBoxLayout(contenido)
        cuerpo.setContentsMargins(18, 16, 18, 14)
        cuerpo.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        cuerpo.addWidget(self.splitter)
        raiz.addWidget(contenido, 1)

        self.splitter.addWidget(self._construir_formulario())
        self.splitter.addWidget(self._construir_editor())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([420, 940])

        raiz.addWidget(self._construir_barra_acciones())

        # Timer para no regenerar la vista previa en cada tecla
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._actualizar_preview)
        self._modo_compacto = False
        self._aplicar_modo_compacto(self.width())

    def _construir_barra_acciones(self) -> QWidget:
        barra = QFrame()
        barra.setObjectName("barraAcciones")
        fila = QHBoxLayout(barra)
        fila.setContentsMargins(20, 10, 20, 10)
        fila.setSpacing(10)

        self.lbl_estado = QLabel("Listo para generar")
        self.lbl_estado.setObjectName("estadoListo")
        fila.addWidget(self.lbl_estado)
        fila.addStretch(1)

        self.btn_copiar = QPushButton("Copiar texto")
        self.btn_copiar.setObjectName("primario")
        self.btn_copiar.setMinimumHeight(40)
        self.btn_copiar.setShortcut("Ctrl+Return")
        self.btn_copiar.setToolTip("Copiar el texto para WhatsApp o correo (Ctrl+Entrar)")
        self.btn_copiar.clicked.connect(self._copiar_texto)
        fila.addWidget(self.btn_copiar)

        self.btn_pdf = QPushButton("Guardar PDF…")
        self.btn_pdf.setMinimumHeight(40)
        self.btn_pdf.clicked.connect(lambda: self._guardar_pdf(abrir=False))
        fila.addWidget(self.btn_pdf)

        self.btn_siguiente = QPushButton("Guardar y siguiente cliente")
        self.btn_siguiente.setMinimumHeight(40)
        self.btn_siguiente.clicked.connect(lambda: self._guardar_y_siguiente(abrir=False))
        fila.addWidget(self.btn_siguiente)

        self.btn_guardar_abrir = QPushButton("Guardar y abrir")
        self.btn_guardar_abrir.clicked.connect(lambda: self._guardar_pdf(abrir=True))
        fila.addWidget(self.btn_guardar_abrir)

        self.btn_carpeta = QToolButton()
        self.btn_carpeta.setText("Carpeta de PDF…")
        self.btn_carpeta.setToolTip("Cambiar dónde se guardan los PDF")
        self.btn_carpeta.clicked.connect(self._elegir_carpeta_destino)
        fila.addWidget(self.btn_carpeta)

        self.lbl_destino = QLabel("")
        self.lbl_destino.setObjectName("rutaDestino")
        self.lbl_destino.setVisible(False)
        self._actualizar_destino_ui()
        return barra

    def _construir_formulario(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panelFormulario")
        self.panel_formulario = panel
        panel.setMinimumWidth(300)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setMinimumWidth(380)
        form_scroll.setWidget(panel)
        form_scroll.setFrameShape(QFrame.NoFrame)
        col = QVBoxLayout(panel)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(12)

        titulo = QLabel("Nuevo aviso")
        titulo.setObjectName("tituloSeccion")
        ayuda = QLabel("El periodo y la fecha se calculan automáticamente.")
        ayuda.setObjectName("textoSuave")
        ayuda.setWordWrap(True)
        col.addWidget(titulo)
        col.addWidget(ayuda)

        gb_pl = QGroupBox("Plantilla")
        ly_pl = QVBoxLayout(gb_pl)
        self.cmb_plantilla = ComboSinRueda()
        for p in self._plantillas_ordenadas():
            self.cmb_plantilla.addItem(p.nombre, p.id)
            self.cmb_plantilla.setItemData(
                self.cmb_plantilla.count() - 1, f"{p.grupo}\n{p.nombre}", Qt.ToolTipRole)
        _ajustar_desplegable(self.cmb_plantilla)
        self.cmb_plantilla.currentIndexChanged.connect(
            lambda: self._on_plantilla_cambia(forzar_docs=not self._docs_tocados))
        ly_pl.addWidget(self.cmb_plantilla)
        self.lbl_grupo_plantilla = QLabel("")
        self.lbl_grupo_plantilla.setObjectName("textoSuave")
        ly_pl.addWidget(self.lbl_grupo_plantilla)
        col.addWidget(gb_pl)

        gb_d = QGroupBox("Datos del aviso")
        ly_d = QFormLayout(gb_d)
        ly_d.setLabelAlignment(Qt.AlignRight)

        periodo_widget = QWidget()
        fila_periodo = QHBoxLayout(periodo_widget)
        fila_periodo.setContentsMargins(0, 0, 0, 0)
        fila_periodo.setSpacing(3)
        self.grupo_periodo = QButtonGroup(self)
        self.grupo_periodo.setExclusive(True)
        self.btns_periodo: dict[str, QPushButton] = {}
        for clave in T.PERIODOS:
            texto = "Renta" if clave == "RENTA" else clave
            btn = QPushButton(texto)
            btn.setObjectName("segmento")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, c=clave: self._on_periodo_boton(c))
            self.grupo_periodo.addButton(btn)
            self.btns_periodo[clave] = btn
            fila_periodo.addWidget(btn)
        ly_d.addRow("Periodo:", periodo_widget)

        self.spin_anio = SpinSinRueda()
        self.spin_anio.setRange(2000, 2100)
        self.spin_anio.setValue(date.today().year)
        self.spin_anio.setMinimumWidth(76)
        self.spin_anio.valueChanged.connect(self._on_periodo_cambia)

        fecha_widget = QWidget()
        fila_fecha = QHBoxLayout(fecha_widget)
        fila_fecha.setContentsMargins(0, 0, 0, 0)
        fila_fecha.setSpacing(8)
        fila_fecha.addWidget(QLabel("Año"))
        fila_fecha.addWidget(self.spin_anio)

        self.txt_cliente = QLineEdit()
        self.txt_cliente.setPlaceholderText("Buscar por nombre…")
        self.txt_cliente.setClearButtonEnabled(True)
        self.txt_cliente.textChanged.connect(self._on_cliente_cambia)
        cliente_widget = QWidget()
        fila_cliente = QHBoxLayout(cliente_widget)
        fila_cliente.setContentsMargins(0, 0, 0, 0)
        fila_cliente.setSpacing(5)
        fila_cliente.addWidget(self.txt_cliente, 1)
        btn_nuevo_cliente = QToolButton()
        btn_nuevo_cliente.setText("+")
        btn_nuevo_cliente.setToolTip("Añadir un cliente nuevo")
        btn_nuevo_cliente.clicked.connect(self._nuevo_cliente_rapido)
        fila_cliente.addWidget(btn_nuevo_cliente)
        self.btn_editar_cliente = QToolButton()
        self.btn_editar_cliente.setText("Editar")
        self.btn_editar_cliente.setToolTip("Editar la ficha del cliente seleccionado")
        self.btn_editar_cliente.clicked.connect(self._editar_cliente_rapido)
        fila_cliente.addWidget(self.btn_editar_cliente)
        ly_d.addRow("Cliente:", cliente_widget)
        self.lbl_ficha_cliente = QLabel("Puede dejarse vacío para un aviso genérico")
        self.lbl_ficha_cliente.setObjectName("textoSuave")
        self.lbl_ficha_cliente.setWordWrap(True)
        ly_d.addRow("", self.lbl_ficha_cliente)

        self.txt_nif = QLineEdit()
        self.txt_nif.setPlaceholderText("NIF del cliente")
        self.txt_nif.setClearButtonEnabled(True)
        self.txt_nif.textChanged.connect(self._on_nif_cambia)
        ly_d.addRow("NIF:", self.txt_nif)

        self.date_limite = FechaSinRueda()
        self.date_limite.setCalendarPopup(True)
        self.date_limite.setDisplayFormat("dd/MM/yyyy")
        self.date_limite.setMinimumWidth(112)
        self.date_limite.dateChanged.connect(self._on_fecha_cambia)
        fila_fecha.addWidget(QLabel("Fecha límite"))
        fila_fecha.addWidget(self.date_limite, 1)
        ly_d.addRow(fecha_widget)

        self.lbl_aviso_fecha = QLabel("")
        self.lbl_aviso_fecha.setStyleSheet("color:#B3541E; font-size:11px;")
        self.lbl_aviso_fecha.setWordWrap(True)
        ly_d.addRow("", self.lbl_aviso_fecha)

        self.chk_navidad = QCheckBox("Incluir felicitación navideña")
        self.chk_navidad.stateChanged.connect(self._al_cambiar_datos)
        ly_d.addRow("", self.chk_navidad)

        col.addWidget(gb_d)

        gb_doc = QGroupBox("Documentos solicitados")
        ly_doc = QVBoxLayout(gb_doc)
        pista_docs = QLabel("Doble clic para editar. Mueve la selección con ↑ y ↓.")
        pista_docs.setObjectName("textoSuave")
        ly_doc.addWidget(pista_docs)
        self.lista_docs = QListWidget()
        self.lista_docs.setObjectName("listaDocumentos")
        self.lista_docs.setMinimumHeight(120)
        self.lista_docs.setWordWrap(True)
        self.lista_docs.setResizeMode(QListView.Adjust)
        self.lista_docs.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista_docs.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed |
            QAbstractItemView.SelectedClicked)
        self.lista_docs.itemChanged.connect(self._on_docs_editados)
        ly_doc.addWidget(self.lista_docs)
        fila_docs = QHBoxLayout()
        btn_anadir_doc = QPushButton("+ Añadir")
        btn_anadir_doc.clicked.connect(self._anadir_documento)
        btn_quitar_doc = QPushButton("Quitar")
        btn_quitar_doc.clicked.connect(self._quitar_documento)
        btn_subir_doc = QToolButton()
        btn_subir_doc.setText("↑")
        btn_subir_doc.setToolTip("Subir documento")
        btn_subir_doc.clicked.connect(lambda: self._mover_documento(-1))
        btn_bajar_doc = QToolButton()
        btn_bajar_doc.setText("↓")
        btn_bajar_doc.setToolTip("Bajar documento")
        btn_bajar_doc.clicked.connect(lambda: self._mover_documento(1))
        btn_reset = QPushButton("Restablecer")
        btn_reset.clicked.connect(self._reset_docs)
        fila_docs.addWidget(btn_anadir_doc)
        fila_docs.addWidget(btn_quitar_doc)
        fila_docs.addWidget(btn_subir_doc)
        fila_docs.addWidget(btn_bajar_doc)
        fila_docs.addStretch(1)
        fila_docs.addWidget(btn_reset)
        ly_doc.addLayout(fila_docs)

        fila_extra_titulo = QHBoxLayout()
        fila_extra_titulo.addWidget(QLabel("Bloques opcionales:"))
        fila_extra_titulo.addStretch(1)
        btn_gestionar_extras = QPushButton("Gestionar…")
        btn_gestionar_extras.clicked.connect(self._abrir_extras)
        fila_extra_titulo.addWidget(btn_gestionar_extras)
        ly_doc.addLayout(fila_extra_titulo)
        self.contenedor_extras = QWidget()
        self.grid_extras = QGridLayout(self.contenedor_extras)
        self.grid_extras.setContentsMargins(0, 0, 0, 0)
        self.grid_extras.setSpacing(6)
        ly_doc.addWidget(self.contenedor_extras)

        col.addWidget(gb_doc)

        self.gb_notas = QGroupBox("Notas adicionales")
        self.gb_notas.setCheckable(True)
        self.gb_notas.setChecked(False)
        ly_n = QVBoxLayout(self.gb_notas)
        self.txt_notas = QPlainTextEdit()
        self.txt_notas.setMaximumHeight(70)
        self.txt_notas.textChanged.connect(self._al_cambiar_datos)
        ly_n.addWidget(self.txt_notas)
        self.gb_notas.toggled.connect(self._al_cambiar_datos)
        col.addWidget(self.gb_notas)
        col.addStretch(1)

        return form_scroll

    def _construir_editor(self) -> QWidget:
        contenedor = QWidget()
        contenedor.setObjectName("panelDocumento")
        self.panel_documento = contenedor
        lay = QVBoxLayout(contenedor)
        lay.setContentsMargins(14, 14, 14, 14)

        cab = QHBoxLayout()
        self.lbl_titulo_documento = QLabel("Texto listo para enviar")
        self.lbl_titulo_documento.setObjectName("tituloSeccion")
        cab.addWidget(self.lbl_titulo_documento)
        cab.addStretch(1)
        self.grupo_modo = QButtonGroup(self)
        self.grupo_modo.setExclusive(True)
        self.btn_modo_preview = QPushButton("Vista previa PDF")
        self.btn_modo_preview.setObjectName("segmento")
        self.btn_modo_preview.setCheckable(True)
        self.btn_modo_editor = QPushButton("Texto")
        self.btn_modo_editor.setObjectName("segmento")
        self.btn_modo_editor.setCheckable(True)
        self.grupo_modo.addButton(self.btn_modo_preview)
        self.grupo_modo.addButton(self.btn_modo_editor)
        self.btn_modo_preview.clicked.connect(lambda: self._mostrar_modo(0))
        self.btn_modo_editor.clicked.connect(lambda: self._mostrar_modo(1))
        cab.addWidget(self.btn_modo_preview)
        cab.addWidget(self.btn_modo_editor)
        lay.addLayout(cab)
        ayuda = QLabel(
            "Este es el texto plano que puedes copiar y pegar en WhatsApp o correo. "
            "También puedes guardarlo como PDF.")
        ayuda.setObjectName("textoSuave")
        lay.addWidget(ayuda)

        self.paginas_documento = QStackedWidget()

        # --- Vista previa permanente ---
        prev_tab = QWidget()
        prev_lay = QVBoxLayout(prev_tab)
        prev_lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_desborda = QLabel(
            "⚠ El texto no cabe en una sola página. Acórtalo o reduce el "
            "tamaño de letra desde Herramientas → Formato del documento.")
        self.lbl_desborda.setStyleSheet(
            "color:#8A2C0D; background:#FBE4D8; padding:6px; border-radius:4px;")
        self.lbl_desborda.setWordWrap(True)
        self.lbl_desborda.setVisible(False)
        prev_lay.addWidget(self.lbl_desborda)
        self.preview = PreviewPanel()
        prev_lay.addWidget(self.preview, 1)
        self.paginas_documento.addWidget(prev_tab)

        # --- Editor accesible sin cambiar el flujo principal ---
        doc_tab = QWidget()
        doc_lay = QVBoxLayout(doc_tab)
        doc_lay.setContentsMargins(0, 0, 0, 0)

        # Aviso de "datos cambiados" cuando el texto esta editado a mano
        self.banner_datos = QWidget()
        bl = QHBoxLayout(self.banner_datos)
        bl.setContentsMargins(8, 4, 8, 4)
        lbl_banner = QLabel("Has editado el texto a mano. Si quieres aplicar los "
                            "datos del formulario, se reescribirá el aviso.")
        lbl_banner.setWordWrap(True)
        btn_actualizar = QPushButton("Reescribir con el formulario")
        btn_actualizar.clicked.connect(self._regenerar_editor)
        bl.addWidget(lbl_banner, 1)
        bl.addWidget(btn_actualizar)
        self.banner_datos.setStyleSheet("background:#FBF3DD; border:1px solid #E4D6A8;")
        self.banner_datos.setVisible(False)
        doc_lay.addWidget(self.banner_datos)

        doc_lay.addLayout(self._construir_barra_formato())

        self.editor = QTextEdit()
        self.editor.setObjectName("editorDocumento")
        self.editor.setAcceptRichText(True)
        self.editor.textChanged.connect(self._on_editor_cambiado)
        self.editor.cursorPositionChanged.connect(self._sincronizar_barra_formato)
        doc_lay.addWidget(self.editor, 1)

        pista = QLabel("El logo y el pie de página se añaden automáticamente al PDF. "
                       "Puedes editar el texto libremente (líneas, espacios, negrita…).")
        pista.setStyleSheet("color:#777; font-size:11px;")
        pista.setWordWrap(True)
        doc_lay.addWidget(pista)

        self.paginas_documento.addWidget(doc_tab)
        self.paginas_documento.setCurrentIndex(1)
        self.btn_modo_editor.setChecked(True)
        lay.addWidget(self.paginas_documento, 1)
        return contenedor

    def _construir_barra_formato(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        barra.setSpacing(4)

        def boton(texto, tooltip, slot, checkable=False):
            b = QToolButton()
            b.setText(texto)
            b.setToolTip(tooltip)
            b.setCheckable(checkable)
            b.clicked.connect(slot)
            barra.addWidget(b)
            return b

        fb = QFont()
        fb.setBold(True)
        self.btn_negrita = boton("N", "Negrita (Ctrl+B)", self._fmt_negrita, checkable=True)
        self.btn_negrita.setFont(fb)
        fi = QFont()
        fi.setItalic(True)
        self.btn_cursiva = boton("C", "Cursiva (Ctrl+I)", self._fmt_cursiva, checkable=True)
        self.btn_cursiva.setFont(fi)
        boton("• Lista", "Lista con viñetas", self._fmt_lista)
        barra.addSpacing(10)
        boton("⯇", "Alinear a la izquierda", lambda: self.editor.setAlignment(Qt.AlignLeft))
        boton("≡", "Centrar", lambda: self.editor.setAlignment(Qt.AlignHCenter))
        barra.addStretch(1)

        self.btn_guardar_def = QPushButton("Guardar como predeterminado")
        self.btn_guardar_def.setToolTip(
            "Convierte este texto en el texto base para todos los futuros avisos "
            "de este tipo (los datos se seguirán rellenando solos)")
        self.btn_guardar_def.clicked.connect(self._guardar_como_predeterminado)
        barra.addWidget(self.btn_guardar_def)

        self.btn_restaurar = QPushButton("Restaurar texto de la plantilla")
        self.btn_restaurar.setToolTip(
            "Vuelve al texto predefinido con los datos actuales del formulario")
        self.btn_restaurar.clicked.connect(self._restaurar_texto)
        barra.addWidget(self.btn_restaurar)
        return barra

    def _aplicar_modo_compacto(self, ancho: int) -> None:
        """Ajusta accesos redundantes y etiquetas sin retirar acciones esenciales."""
        if not hasattr(self, "btn_copiar"):
            return
        compacto = ancho < 1180
        self._modo_compacto = compacto
        self.btn_carpeta.setVisible(not compacto)
        for boton in self._acciones_cabecera:
            boton.setVisible(not compacto)
        self.btn_pdf.setText("Guardar PDF" if compacto else "Guardar PDF…")
        self.btn_siguiente.setText(
            "Guardar y siguiente" if compacto else "Guardar y siguiente cliente")
        self.btn_guardar_def.setText(
            "Guardar base" if compacto else "Guardar como predeterminado")
        self.btn_restaurar.setText(
            "Restaurar plantilla" if compacto else "Restaurar texto de la plantilla")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._aplicar_modo_compacto(event.size().width())

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._comprobacion_inicial_hecha:
            self._comprobacion_inicial_hecha = True
            QTimer.singleShot(3000, self._comprobar_actualizacion_periodica)

    # --------------------------------------------------------------- estado
    def _plantillas_ordenadas(self) -> list[T.Plantilla]:
        usos = self._ajustes().get("uso_plantillas", {})
        posiciones = {p.id: i for i, p in enumerate(T.PLANTILLAS)}
        return sorted(T.PLANTILLAS,
                      key=lambda p: (-int(usos.get(p.id, 0)), posiciones[p.id]))

    def _plantilla_actual(self) -> T.Plantilla:
        return T.por_id(self.cmb_plantilla.currentData())

    def _periodo_actual(self) -> str:
        for clave, boton in self.btns_periodo.items():
            if boton.isChecked():
                return clave
        return "1T"

    def _documentos_actuales(self) -> list[str]:
        return [self.lista_docs.item(i).text().strip()
                for i in range(self.lista_docs.count())
                if self.lista_docs.item(i).text().strip()]

    def _extras_etiquetas_marcadas(self) -> list[str]:
        return [etiqueta for etiqueta, boton in self._extra_buttons.items()
                if boton.isChecked()]

    def _contexto(self) -> T.Contexto:
        qd = self.date_limite.date()
        return T.Contexto(
            periodo=self._periodo_actual(),
            anio=self.spin_anio.value(),
            cliente=self.txt_cliente.text(),
            nif=self.txt_nif.text(),
            fecha_limite=date(qd.year(), qd.month(), qd.day()),
            documentos=self._documentos_actuales(),
            documentos_extra=self._extras_marcados(),
            navidad=self.chk_navidad.isChecked(),
            notas=self.txt_notas.toPlainText() if self.gb_notas.isChecked() else "",
        )

    def _extras_marcados(self) -> list[tuple[str, list[str]]]:
        disponibles = {e.etiqueta: e for e in X.cargar()}
        return [(disponibles[e].intro, disponibles[e].lineas)
                for e in self._extras_etiquetas_marcadas() if e in disponibles]

    def _aplicar_periodo_sugerido(self) -> None:
        clave, anio = T.periodo_sugerido_hoy()
        self._set_periodo(clave)
        self.spin_anio.blockSignals(True)
        self.spin_anio.setValue(anio)
        self.spin_anio.blockSignals(False)
        self._actualizar_fecha_desde_periodo()

    def _on_plantilla_cambia(self, forzar_docs: bool = True) -> None:
        p = self._plantilla_actual()
        self.lbl_grupo_plantilla.setText(p.grupo)
        self.chk_navidad.setVisible(p.usa_navidad)
        if p.id == "cierre_anual":
            self._set_periodo("4T")
        elif p.id == "renta_arrend":
            self._set_periodo("RENTA")
        if forzar_docs:
            self._set_docs(p.documentos_def)
        self._actualizar_fecha_desde_periodo()
        self._al_cambiar_datos()

    def _actualizar_fecha_desde_periodo(self) -> None:
        clave = self._periodo_actual()
        d = T.plazo_por_defecto(clave, self.spin_anio.value())
        self.date_limite.blockSignals(True)
        self.date_limite.setDate(QDate(d.year, d.month, d.day))
        self.date_limite.blockSignals(False)
        self._actualizar_aviso_fecha()

    def _on_periodo_cambia(self) -> None:
        self._actualizar_fecha_desde_periodo()
        self._al_cambiar_datos()

    def _on_periodo_boton(self, clave: str) -> None:
        self._set_periodo(clave)
        self._on_periodo_cambia()

    def _on_fecha_cambia(self) -> None:
        self._actualizar_aviso_fecha()
        self._al_cambiar_datos()

    def _actualizar_aviso_fecha(self) -> None:
        qd = self.date_limite.date()
        d = date(qd.year(), qd.month(), qd.day())
        aviso = T.aviso_fecha(d)
        self.lbl_aviso_fecha.setText(f"⚠ {aviso}" if aviso else "")

    def _on_docs_editados(self, item: QListWidgetItem | None = None) -> None:
        if item is not None:
            bloqueado = self.lista_docs.blockSignals(True)
            self._ajustar_alto_documento(item)
            self.lista_docs.blockSignals(bloqueado)
        self._docs_tocados = True
        self._al_cambiar_datos()

    def _set_docs(self, docs: list[str]) -> None:
        self._undo_documento = None
        self.lista_docs.blockSignals(True)
        self.lista_docs.clear()
        for texto in docs:
            item = QListWidgetItem(texto)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setToolTip(texto)
            self._ajustar_alto_documento(item)
            self.lista_docs.addItem(item)
        self.lista_docs.blockSignals(False)
        self._docs_tocados = False
        self._desmarcar_extras()

    def _anadir_documento(self) -> None:
        item = QListWidgetItem("Nuevo documento")
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._ajustar_alto_documento(item)
        self.lista_docs.addItem(item)
        self.lista_docs.setCurrentItem(item)
        self.lista_docs.editItem(item)
        self._on_docs_editados()

    def _ajustar_alto_documento(self, item: QListWidgetItem) -> None:
        ancho = max(self.lista_docs.viewport().width() - 26, 260)
        alto = self.lista_docs.fontMetrics().boundingRect(
            0, 0, ancho, 1000, Qt.TextWordWrap, item.text()).height() + 16
        item.setSizeHint(QSize(0, max(72, alto)))
        item.setToolTip(item.text())

    def _quitar_documento(self) -> None:
        fila = self.lista_docs.currentRow()
        if fila >= 0:
            eliminado = self.lista_docs.takeItem(fila)
            self._undo_documento = (fila, eliminado.text())
            self._on_docs_editados()

    def _deshacer_eliminacion_documento(self) -> None:
        if self._undo_documento is None:
            return
        fila, texto = self._undo_documento
        item = QListWidgetItem(texto)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._ajustar_alto_documento(item)
        self.lista_docs.insertItem(min(fila, self.lista_docs.count()), item)
        self.lista_docs.setCurrentItem(item)
        self._undo_documento = None
        self._on_docs_editados()

    def _mover_documento(self, delta: int) -> None:
        fila = self.lista_docs.currentRow()
        destino = fila + delta
        if fila < 0 or destino < 0 or destino >= self.lista_docs.count():
            return
        item = self.lista_docs.takeItem(fila)
        self.lista_docs.insertItem(destino, item)
        self.lista_docs.setCurrentRow(destino)
        self._on_docs_editados()

    def _reset_docs(self) -> None:
        self._set_docs(self._plantilla_actual().documentos_def)
        self._al_cambiar_datos()

    # ------------------------------------------------------- doc. opcional
    def _refrescar_lista_extras(self) -> None:
        marcados = set(self._extras_etiquetas_marcadas())
        while self.grid_extras.count():
            item = self.grid_extras.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._extra_buttons.clear()
        for indice, extra in enumerate(sorted(X.cargar(), key=lambda e: e.etiqueta.lower())):
            boton = QToolButton()
            boton.setObjectName("etiquetaOpcional")
            boton.setText(extra.etiqueta)
            boton.setCheckable(True)
            boton.setChecked(extra.etiqueta in marcados)
            resumen = (f"{extra.intro}\n" if extra.intro else "") + "\n".join(f"• {ln}" for ln in extra.lineas)
            boton.setToolTip(resumen)
            boton.toggled.connect(self._on_extra_marcado)
            self._extra_buttons[extra.etiqueta] = boton
            self.grid_extras.addWidget(boton, indice // 2, indice % 2)
        if not self._extra_buttons:
            vacio = QLabel("Aún no hay bloques opcionales guardados")
            vacio.setObjectName("textoSuave")
            self.grid_extras.addWidget(vacio, 0, 0, 1, 2)

    def _desmarcar_extras(self) -> None:
        for boton in self._extra_buttons.values():
            boton.blockSignals(True)
            boton.setChecked(False)
            boton.blockSignals(False)

    def _on_extra_marcado(self, _marcado: bool = False) -> None:
        # La documentacion opcional se guarda aparte (T.Contexto.documentos_extra)
        # y se inserta como su propio parrafo/lista: no se mezcla con la
        # lista base de "Documentos solicitados".
        self._al_cambiar_datos()

    def _abrir_extras(self) -> None:
        ExtrasDialog(self).exec()
        self._refrescar_lista_extras()

    def _set_periodo(self, clave: str) -> None:
        if clave not in self.btns_periodo:
            return
        for c, boton in self.btns_periodo.items():
            boton.blockSignals(True)
            boton.setChecked(c == clave)
            boton.blockSignals(False)

    def _refrescar_completer_clientes(self) -> None:
        recientes = {nombre.casefold(): i for i, nombre in enumerate(H.clientes_recientes())}
        clientes = C.cargar()
        clientes.sort(key=lambda c: (
            not c.favorito,
            recientes.get(c.nombre.casefold(), len(recientes)),
            *clave_orden_cliente(c)[1:],
        ))
        opciones = [f"{c.nombre} · {c.nif}" if c.nif else c.nombre for c in clientes]
        modelo = QStringListModel(opciones, self)
        completer = QCompleter(modelo, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.activated[str].connect(self._cliente_autocompletado)
        self.txt_cliente.setCompleter(completer)
        self._actualizar_ficha_cliente()

    def _cliente_autocompletado(self, texto: str) -> None:
        self.txt_cliente.setText(texto.split(" · ", 1)[0])

    def _on_cliente_cambia(self) -> None:
        self._actualizar_ficha_cliente()
        self._al_cambiar_datos()

    def _on_nif_cambia(self) -> None:
        cliente = C.buscar(C.cargar(), self.txt_nif.text())
        if cliente is not None and cliente.nombre != self.txt_cliente.text():
            bloqueado = self.txt_cliente.blockSignals(True)
            self.txt_cliente.setText(cliente.nombre)
            self.txt_cliente.blockSignals(bloqueado)
        self._actualizar_ficha_cliente()
        self._al_cambiar_datos()

    def _actualizar_ficha_cliente(self) -> None:
        cliente = C.buscar(C.cargar(), self.txt_cliente.text())
        self.btn_editar_cliente.setEnabled(cliente is not None)
        if cliente is None:
            self.lbl_ficha_cliente.setText(
                "Puede dejarse vacío para un aviso genérico" if not self.txt_cliente.text().strip()
                else "Cliente nuevo: se guardará al generar el aviso")
            return
        if cliente.nif and self.txt_nif.text() != cliente.nif:
            bloqueado = self.txt_nif.blockSignals(True)
            self.txt_nif.setText(cliente.nif)
            self.txt_nif.blockSignals(bloqueado)
        detalles = [dato for dato in (cliente.nif, cliente.telefono, cliente.email) if dato]
        self.lbl_ficha_cliente.setText(" · ".join(detalles) if detalles else "Cliente guardado")

    def _nuevo_cliente_rapido(self) -> None:
        dlg = EditorClienteDialog(self)
        if dlg.exec() != EditorClienteDialog.Accepted:
            return
        clientes = C.cargar()
        nuevo = dlg.cliente()
        if C.buscar(clientes, nuevo.nombre):
            QMessageBox.warning(self, "Cliente ya existe",
                                f"Ya hay un cliente llamado «{nuevo.nombre}».")
            return
        guardar_clientes_con_conflictos(self, C.upsert(clientes, nuevo))
        self._refrescar_completer_clientes()
        self.txt_cliente.setText(nuevo.nombre)

    def _editar_cliente_rapido(self) -> None:
        clientes = C.cargar()
        actual = C.buscar(clientes, self.txt_cliente.text())
        if actual is None:
            return
        dlg = EditorClienteDialog(self, actual)
        if dlg.exec() == EditorClienteDialog.Accepted:
            editado = dlg.cliente()
            guardar_clientes_con_conflictos(
                self, C.upsert(clientes, editado, actual.nombre)
            )
            self._refrescar_completer_clientes()
            self.txt_cliente.setText(editado.nombre)

    # --------------------------------------------------------------- editor
    def _al_cambiar_datos(self) -> None:
        """Un dato del formulario ha cambiado. Si el texto no se ha tocado
        a mano, se reescribe con los nuevos datos; si se ha editado, se
        avisa (sin pisar lo que el usuario escribio)."""
        if not hasattr(self, "editor"):
            return
        if self._editor_dirty:
            self._datos_pendientes = True
            self.banner_datos.setVisible(True)
            self._set_estado("Hay cambios del formulario pendientes de aplicar", aviso=True)
        else:
            self._regenerar_editor()
        self._programar_borrador()

    def _regenerar_editor(self) -> None:
        est = E.cargar()
        html = R.documento_inicial(self._contexto(), self._plantilla_actual(), est)
        self._cargar_html_editor(html, dirty=False)

    def _cargar_html_editor(self, html: str, *, dirty: bool) -> None:
        est = E.cargar()
        self._cargando_editor = True
        f = QFont(est.fuente)
        f.setPointSizeF(est.tamano_cuerpo)
        self.editor.document().setDefaultFont(f)
        self.editor.document().setDefaultStyleSheet(R.stylesheet(est))
        self.editor.setHtml(html)
        R.aplicar_margenes_bloques(self.editor.document(), est)
        self._cargando_editor = False
        self._editor_dirty = dirty
        self._datos_pendientes = False
        self.banner_datos.setVisible(False)
        if self.paginas_documento.currentIndex() == 0:
            self._actualizar_preview()
        else:
            self._programar_preview()

    def _restaurar_texto(self) -> None:
        if self._editor_dirty:
            resp = QMessageBox.question(
                self, "Restaurar texto",
                "Se descartarán los cambios que hayas hecho a mano y se volverá "
                "al texto de la plantilla con los datos actuales. ¿Continuar?",
                QMessageBox.Yes | QMessageBox.No)
            if resp != QMessageBox.Yes:
                return
        self._regenerar_editor()

    def _guardar_como_predeterminado(self) -> None:
        p = self._plantilla_actual()
        ctx = self._contexto()
        mensaje = (
            f"Se guardará el texto actual como el texto base de «{p.nombre}», "
            "para todos los avisos futuros de este tipo.\n\n"
            "Los datos de cliente, periodo y fecha se seguirán rellenando "
            "automáticamente. Podrás revisarlo o deshacerlo en "
            "Herramientas → Editar plantillas.")
        if ctx.documentos_extra:
            mensaje += ("\n\n⚠ Tienes documentación opcional marcada. No se incluirá en el "
                        "texto base guardado (la documentación opcional sigue siendo "
                        "opcional, se añade aparte en cada aviso).")
        resp = QMessageBox.question(
            self, "Guardar como predeterminado", mensaje + "\n\n¿Continuar?",
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        try:
            titulo, cuerpo = R.documento_a_plantilla(self.editor.document(), ctx)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el texto:\n{e}")
            return
        if not titulo.strip() or not cuerpo.strip():
            QMessageBox.warning(self, "No se pudo guardar",
                                 "El documento parece estar vacío.")
            return
        T.guardar_override(p.id, titulo, cuerpo)
        self._editor_dirty = False
        self._datos_pendientes = False
        self.banner_datos.setVisible(False)
        QMessageBox.information(
            self, "Guardado",
            f"Guardado como texto predeterminado de «{p.nombre}».\n"
            "Se usará en los próximos avisos de este tipo.")

    def _on_editor_cambiado(self) -> None:
        if self._cargando_editor:
            return
        self._editor_dirty = True
        self._programar_preview()
        self._programar_borrador()

    # ---------------------------------------------------------- borrador
    def _programar_borrador(self) -> None:
        if (not self._restaurando_borrador and
                hasattr(self, "_timer_borrador")):
            self._timer_borrador.start()

    def _serializar_borrador(self) -> dict:
        qd = self.date_limite.date()
        return {
            "plantilla_id": self.cmb_plantilla.currentData(),
            "cliente": self.txt_cliente.text(),
            "nif": self.txt_nif.text(),
            "periodo": self._periodo_actual(),
            "anio": self.spin_anio.value(),
            "fecha_limite": qd.toString(Qt.ISODate),
            "documentos": self._documentos_actuales(),
            "extras": self._extras_etiquetas_marcadas(),
            "navidad": self.chk_navidad.isChecked(),
            "notas_activas": self.gb_notas.isChecked(),
            "notas": self.txt_notas.toPlainText(),
            "editor_html": self.editor.toHtml(),
            "editor_dirty": self._editor_dirty,
            "datos_pendientes": self._datos_pendientes,
            "carpeta_destino": self._carpeta_destino,
        }

    def _guardar_borrador_ahora(self) -> None:
        if self._restaurando_borrador:
            return
        try:
            guardar_borrador(self._serializar_borrador())
        except Exception:
            logger.exception("No se pudo guardar el borrador recuperable")

    def _restaurar_borrador(self, datos: dict) -> None:
        self._restaurando_borrador = True
        try:
            indice = self.cmb_plantilla.findData(datos.get("plantilla_id"))
            if indice >= 0:
                bloqueado = self.cmb_plantilla.blockSignals(True)
                self.cmb_plantilla.setCurrentIndex(indice)
                self.cmb_plantilla.blockSignals(bloqueado)
            self._set_periodo(str(datos.get("periodo", "1T")))
            bloqueado = self.spin_anio.blockSignals(True)
            self.spin_anio.setValue(int(datos.get("anio", self.spin_anio.value())))
            self.spin_anio.blockSignals(bloqueado)
            fecha = QDate.fromString(str(datos.get("fecha_limite", "")), Qt.ISODate)
            if fecha.isValid():
                bloqueado = self.date_limite.blockSignals(True)
                self.date_limite.setDate(fecha)
                self.date_limite.blockSignals(bloqueado)
            for campo, valor in (
                (self.txt_cliente, datos.get("cliente", "")),
                (self.txt_nif, datos.get("nif", "")),
            ):
                bloqueado = campo.blockSignals(True)
                campo.setText(str(valor))
                campo.blockSignals(bloqueado)
            documentos = datos.get("documentos")
            if isinstance(documentos, list):
                self._set_docs([str(x) for x in documentos])
            self._refrescar_lista_extras()
            extras = datos.get("extras", [])
            for etiqueta in extras if isinstance(extras, list) else []:
                if etiqueta in self._extra_buttons:
                    self._extra_buttons[etiqueta].setChecked(True)
            bloqueado = self.chk_navidad.blockSignals(True)
            self.chk_navidad.setChecked(bool(datos.get("navidad", False)))
            self.chk_navidad.blockSignals(bloqueado)
            bloqueado = self.gb_notas.blockSignals(True)
            self.gb_notas.setChecked(bool(datos.get("notas_activas", False)))
            self.gb_notas.blockSignals(bloqueado)
            bloqueado = self.txt_notas.blockSignals(True)
            self.txt_notas.setPlainText(str(datos.get("notas", "")))
            self.txt_notas.blockSignals(bloqueado)
            carpeta = datos.get("carpeta_destino")
            if carpeta:
                self._carpeta_destino = str(carpeta)
                self._actualizar_destino_ui()
            html = datos.get("editor_html")
            if isinstance(html, str) and html.strip():
                self._cargar_html_editor(html, dirty=bool(datos.get("editor_dirty", False)))
                self._datos_pendientes = bool(datos.get("datos_pendientes", False))
                self.banner_datos.setVisible(self._datos_pendientes)
            else:
                self._regenerar_editor()
            self._actualizar_ficha_cliente()
        finally:
            self._restaurando_borrador = False

    def _deshacer_cambio_cliente(self) -> None:
        if self._undo_cliente:
            datos, self._undo_cliente = self._undo_cliente, None
            self._restaurar_borrador(datos)
            self._guardar_borrador_ahora()

    # --- barra de formato ---
    def _fmt_negrita(self) -> None:
        peso = QFont.Normal if self.editor.fontWeight() > QFont.Normal else QFont.Bold
        self.editor.setFontWeight(peso)
        self.editor.setFocus()

    def _fmt_cursiva(self) -> None:
        self.editor.setFontItalic(not self.editor.fontItalic())
        self.editor.setFocus()

    def _fmt_lista(self) -> None:
        self.editor.textCursor().createList(QTextListFormat.ListDisc)
        self.editor.setFocus()

    def _sincronizar_barra_formato(self) -> None:
        self.btn_negrita.setChecked(self.editor.fontWeight() > QFont.Normal)
        self.btn_cursiva.setChecked(self.editor.fontItalic())

    def keyPressEvent(self, event) -> None:  # noqa: N802 (atajos Ctrl+B / Ctrl+I)
        if event.modifiers() & Qt.ControlModifier and self.editor.hasFocus():
            if event.key() == Qt.Key_B:
                self._fmt_negrita()
                return
            if event.key() == Qt.Key_I:
                self._fmt_cursiva()
                return
        super().keyPressEvent(event)

    # -------------------------------------------------------------- preview
    def _mostrar_modo(self, indice: int) -> None:
        self.paginas_documento.setCurrentIndex(indice)
        self.lbl_titulo_documento.setText(
            "Vista previa PDF" if indice == 0 else "Texto listo para enviar")
        self.btn_modo_preview.setChecked(indice == 0)
        self.btn_modo_editor.setChecked(indice == 1)
        if indice == 0:
            self._actualizar_preview()

    def _copiar_texto(self) -> None:
        """Copia el aviso sin formato para pegarlo en WhatsApp o correo."""
        if not self._resolver_datos_pendientes():
            return
        texto = self.editor.toPlainText().strip()
        if not texto:
            QMessageBox.warning(self, "Aviso vacío", "No hay texto para copiar.")
            return
        QApplication.clipboard().setText(texto)
        self._registrar_uso_plantilla()
        self._set_estado("Texto copiado. Ya puedes pegarlo en WhatsApp o correo.")

    def _programar_preview(self) -> None:
        self._timer.start()

    def _actualizar_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        html = self.editor.toHtml()

        def generador(dpi, info):
            return R.render_preview_documento(html, dpi=dpi, info=info, est=E.cargar())

        info = self.preview.mostrar(generador)
        desborda = bool(info.get("desborda"))
        self.lbl_desborda.setVisible(desborda)
        if desborda:
            self._set_estado("El aviso ocupa más de una página", aviso=True)
        elif self._datos_pendientes:
            self._set_estado("Hay cambios del formulario pendientes de aplicar", aviso=True)
        else:
            self._set_estado("Listo para generar")

    def _set_estado(self, texto: str, *, aviso: bool = False) -> None:
        if not hasattr(self, "lbl_estado"):
            return
        self.lbl_estado.setText(texto)
        self.lbl_estado.setObjectName("estadoAviso" if aviso else "estadoListo")
        self.lbl_estado.style().unpolish(self.lbl_estado)
        self.lbl_estado.style().polish(self.lbl_estado)

    # ----------------------------------------------------------------- PDF
    def _instantanea_documento(self) -> tuple[str, str]:
        try:
            titulo, cuerpo = R.documento_a_plantilla(self.editor.document(), self._contexto())
            if titulo.strip() and cuerpo.strip():
                return titulo, cuerpo
        except Exception:
            logger.exception("No se pudo crear la instantanea editable del aviso")
        p = self._plantilla_actual()
        return T.titulo_tpl_activo(p), T.cuerpo_tpl_activo(p)

    def _resolver_datos_pendientes(self) -> bool:
        if not self._datos_pendientes:
            return True
        caja = QMessageBox(self)
        caja.setWindowTitle("Cambios pendientes")
        caja.setIcon(QMessageBox.Warning)
        caja.setText(
            "Has cambiado datos del formulario después de editar el texto. "
            "¿Quieres aplicarlos antes de generar?")
        aplicar = caja.addButton("Aplicar datos", QMessageBox.AcceptRole)
        actual = caja.addButton("Generar el texto actual", QMessageBox.ActionRole)
        caja.addButton("Cancelar", QMessageBox.RejectRole)
        caja.exec()
        if caja.clickedButton() is aplicar:
            self._regenerar_editor()
            return True
        return caja.clickedButton() is actual

    def _guardar_pdf(self, abrir: bool = False, *, mostrar_confirmacion: bool = True,
                     resolver_pendientes: bool = True) -> Path | None:
        if resolver_pendientes and not self._resolver_datos_pendientes():
            return None
        ctx = self._contexto()
        plantilla = self._plantilla_actual()
        carpeta = Path(self._carpeta_destino)
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Carpeta no válida",
                                f"No se puede usar la carpeta de destino:\n{e}")
            return None
        destino = ruta_sin_colision(carpeta, nombre_archivo(plantilla, ctx))

        info: dict = {}
        try:
            R.render_pdf_documento(self.editor.toHtml(), destino, info=info, est=E.cargar())
        except Exception as e:
            logger.exception("Fallo al generar el PDF %s", destino)
            QMessageBox.critical(self, "Error", f"No se pudo generar el PDF:\n{e}")
            return None

        logger.info("PDF generado: %s (%s %s, cliente=%s)",
                    destino.name, ctx.periodo_corto, ctx.anio, ctx.cliente or "(generico)")
        titulo_tpl, cuerpo_tpl = self._instantanea_documento()
        H.registrar(
            plantilla.nombre, ctx.periodo_corto, ctx.anio, ctx.cliente, str(destino),
            plantilla_id=plantilla.id, documentos=ctx.documentos,
            extras=self._extras_etiquetas_marcadas(), navidad=ctx.navidad,
            notas=ctx.notas, titulo_tpl=titulo_tpl, cuerpo_tpl=cuerpo_tpl,
        )
        if C.asegurar_cliente(ctx.cliente, ctx.nif):
            self._refrescar_completer_clientes()
        C.registrar_uso(ctx.cliente)
        self._registrar_uso_plantilla()
        self._guardar_ajustes(carpeta)
        self._set_estado(f"PDF generado: {destino.name}")

        if abrir:
            self._abrir_ruta(destino)
            return destino

        if not mostrar_confirmacion:
            return destino

        mensaje = f"Aviso guardado en:\n{destino}"
        if info.get("desborda"):
            mensaje += "\n\n⚠ Aviso: el texto no cabía en una sola página; revisa el PDF."
        caja = QMessageBox(self)
        caja.setWindowTitle("PDF generado")
        caja.setIcon(QMessageBox.Information)
        caja.setText(mensaje)
        btn_abrir = caja.addButton("Abrir PDF", QMessageBox.ActionRole)
        btn_carpeta = caja.addButton("Abrir carpeta", QMessageBox.ActionRole)
        btn_otro = caja.addButton("Mantener datos y cambiar cliente", QMessageBox.ActionRole)
        caja.addButton("Cerrar", QMessageBox.AcceptRole)
        caja.exec()
        pulsado = caja.clickedButton()
        if pulsado is btn_abrir:
            self._abrir_ruta(destino)
        elif pulsado is btn_carpeta:
            self._abrir_ruta(destino.parent)
        elif pulsado is btn_otro:
            documento_tpl = self._instantanea_documento()
            self._limpiar_para_siguiente(documento_tpl, self._editor_dirty)
        return destino

    def _limpiar_para_siguiente(self, documento_tpl: tuple[str, str], dirty: bool) -> None:
        self._undo_cliente = self._serializar_borrador()
        for campo in (self.txt_cliente, self.txt_nif):
            bloqueado = campo.blockSignals(True)
            campo.clear()
            campo.blockSignals(bloqueado)
        titulo_tpl, cuerpo_tpl = documento_tpl
        ctx = self._contexto()
        html = R.componer_documento(
            T.render_titulo_texto(ctx, titulo_tpl),
            T.render_cuerpo_texto(ctx, cuerpo_tpl),
            E.cargar(),
        )
        self._cargar_html_editor(html, dirty=dirty)
        self._actualizar_ficha_cliente()
        self.txt_cliente.setFocus()
        self._guardar_borrador_ahora()

    def _guardar_y_siguiente(self, abrir: bool = False) -> Path | None:
        if not self._resolver_datos_pendientes():
            return None
        documento_tpl = self._instantanea_documento()
        dirty = self._editor_dirty
        salida = self._guardar_pdf(
            abrir=abrir, mostrar_confirmacion=False, resolver_pendientes=False
        )
        if salida is None:
            return None
        self._limpiar_para_siguiente(documento_tpl, dirty)
        self._set_estado(f"PDF generado: {salida.name} · listo para el siguiente cliente")
        return salida

    def _abrir_ruta(self, ruta: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))

    def _elegir_carpeta_destino(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta para los avisos", self._carpeta_destino)
        if carpeta:
            self._carpeta_destino = carpeta
            self._actualizar_destino_ui()
            self._guardar_ajustes(Path(carpeta))

    def _actualizar_destino_ui(self) -> None:
        if not hasattr(self, "lbl_destino"):
            return
        ruta = Path(self._carpeta_destino)
        texto = ruta.name or str(ruta)
        self.lbl_destino.setText(texto)
        self.lbl_destino.setToolTip(str(ruta))

    def _registrar_uso_plantilla(self) -> None:
        datos = self._ajustes()
        usos = datos.get("uso_plantillas", {})
        if not isinstance(usos, dict):
            usos = {}
        pid = self._plantilla_actual().id
        usos[pid] = int(usos.get(pid, 0)) + 1
        self._actualizar_ajustes(uso_plantillas=usos)

    # ------------------------------------------------------------ herramientas
    def _abrir_clientes(self) -> None:
        ClientesDialog(self).exec()
        self._refrescar_completer_clientes()

    def _abrir_lote(self) -> None:
        if not self._resolver_datos_pendientes():
            return
        documento_tpl = self._instantanea_documento()
        dlg = LoteDialog(
            self, self._contexto(), self._plantilla_actual(), self._carpeta_destino,
            documento_tpl=documento_tpl,
            extras_etiquetas=self._extras_etiquetas_marcadas())
        resultado = dlg.exec()
        self._guardar_ajustes(Path(dlg.carpeta_usada()))
        self._carpeta_destino = dlg.carpeta_usada()
        self._actualizar_destino_ui()
        if resultado == LoteDialog.Accepted:
            self._registrar_uso_plantilla()
        self._refrescar_completer_clientes()

    def _abrir_historial(self) -> None:
        HistorialDialog(self, on_reutilizar=self._reutilizar_historial).exec()

    def _reutilizar_historial(self, entrada: H.Entrada) -> None:
        pid = entrada.plantilla_id
        if not pid:
            encontrada = next((p for p in T.PLANTILLAS if p.nombre == entrada.plantilla), None)
            pid = encontrada.id if encontrada else ""
        indice = self.cmb_plantilla.findData(pid)
        if indice >= 0:
            self.cmb_plantilla.setCurrentIndex(indice)

        periodo = next((clave for clave, info in T.PERIODOS.items()
                        if entrada.periodo in (clave, info["corto"])), "1T")
        self._set_periodo(periodo)
        self.spin_anio.setValue(entrada.anio)
        self.txt_cliente.setText("" if entrada.cliente == "(genérico)" else entrada.cliente)
        self._set_docs(entrada.documentos or self._plantilla_actual().documentos_def)
        self._refrescar_lista_extras()
        for etiqueta in entrada.extras:
            if etiqueta in self._extra_buttons:
                self._extra_buttons[etiqueta].setChecked(True)
        self.chk_navidad.setChecked(entrada.navidad)
        self.gb_notas.setChecked(bool(entrada.notas))
        self.txt_notas.setPlainText(entrada.notas)
        self._actualizar_fecha_desde_periodo()

        if entrada.titulo_tpl and entrada.cuerpo_tpl:
            ctx = self._contexto()
            est = E.cargar()
            html = R.componer_documento(
                T.render_titulo_texto(ctx, entrada.titulo_tpl),
                T.render_cuerpo_texto(ctx, entrada.cuerpo_tpl), est)
            self._cargar_html_editor(html, dirty=True)
        else:
            self._regenerar_editor()
        self._mostrar_modo(0)
        self.raise_()
        self.activateWindow()

    def _abrir_editor_plantillas(self) -> None:
        if self._editor_plantillas is None or not self._editor_plantillas.isVisible():
            self._editor_plantillas = PlantillaEditorDialog(self, on_cambio=self._al_cambiar_desde_dialogo)
        self._editor_plantillas.show()
        self._editor_plantillas.raise_()
        self._editor_plantillas.activateWindow()

    def _abrir_formato(self) -> None:
        if self._editor_formato is None or not self._editor_formato.isVisible():
            self._editor_formato = FormatoDialog(self, on_cambio=self._al_cambiar_desde_dialogo)
        self._editor_formato.show()
        self._editor_formato.raise_()
        self._editor_formato.activateWindow()

    def _al_cambiar_desde_dialogo(self) -> None:
        """Cambio hecho en el editor de plantillas o de formato: si el texto
        no se ha tocado a mano, se reescribe con lo nuevo; si se ha editado,
        se deja como esta (para no perder los cambios) y solo se avisa."""
        if self._editor_dirty:
            self.banner_datos.setVisible(True)
            self._programar_preview()
        else:
            self._regenerar_editor()

    def _buscar_actualizaciones_manual(self) -> None:
        if self._estado_actualizacion == U.ESTADO_LISTA and self._ruta_update_lista:
            self._set_estado("Actualización lista · se instalará al cerrar")
            return
        comprobar_actualizaciones(self, __version__, silencioso=False)

    def _comprobar_actualizacion_periodica(self) -> None:
        if self._estado_actualizacion in (
            U.ESTADO_COMPROBANDO, U.ESTADO_DESCARGANDO, U.ESTADO_LISTA
        ):
            return
        comprobar_actualizaciones(self, __version__, silencioso=True)

    def _actualizacion_estado(self, estado: str) -> None:
        self._estado_actualizacion = estado

    def _actualizacion_lista(self, ruta: str) -> None:
        self._guardar_borrador_ahora()
        self._ruta_update_lista = ruta
        self._instalar_al_cerrar = True
        self._estado_actualizacion = U.ESTADO_LISTA
        self._set_estado("Actualización lista · se instalará al cerrar")

    def _actualizacion_error(self, mensaje: str) -> None:
        if self._estado_actualizacion == U.ESTADO_LISTA and self._ruta_update_lista:
            logger.info("Se conserva la actualización ya preparada: %s", mensaje)
            return
        self._estado_actualizacion = U.ESTADO_ERROR
        logger.info("Actualización pendiente de reintento: %s", mensaje)

    def _instalar_actualizacion_ahora(self) -> None:
        if not self._ruta_update_lista:
            return
        self._guardar_borrador_ahora()
        try:
            iniciar_instalador(self._ruta_update_lista)
        except Exception as exc:
            self._actualizacion_error(str(exc))
            QMessageBox.critical(self, "Error", f"No se pudo iniciar el instalador:\n{exc}")
            return
        self._instalar_al_cerrar = False
        QApplication.instance().quit()

    def _abrir_carpeta_datos(self) -> None:
        """Abre la carpeta donde se guardan clientes, historial, plantillas
        personalizadas y ajustes — util para hacer copias de seguridad."""
        self._abrir_ruta(config.config_dir())

    def _acerca_de(self) -> None:
        QMessageBox.about(
            self, "Acerca de",
            f"<b>{config.APP_NAME}</b><br>Versión {__version__}<br><br>"
            "Generador de avisos a clientes en PDF con la estética de la asesoría.<br><br>"
            f"Novedades y descargas:<br>"
            f"<a href='https://github.com/{config.GITHUB_REPO}/releases'>"
            f"github.com/{config.GITHUB_REPO}/releases</a><br><br>"
            f"Tus datos se guardan en:<br>{config.config_dir()}")

    # ------------------------------------------------------------- ajustes
    def _ajustes(self) -> dict:
        datos = config.leer_json(config.settings_path(), {})
        return datos if isinstance(datos, dict) else {}

    def _actualizar_ajustes(self, **cambios) -> None:
        """Actualiza solo las claves indicadas, conservando el resto."""
        datos = self._ajustes()
        datos.update(cambios)
        try:
            config.escribir_json(config.settings_path(), datos)
        except Exception:
            pass

    def _cargar_ajustes(self) -> None:
        datos = self._ajustes()
        self._carpeta_destino = datos.get("ultima_carpeta") or str(Path.home() / "Desktop")
        self._actualizar_destino_ui()
        pid = datos.get("plantilla")
        if pid:
            idx = self.cmb_plantilla.findData(pid)
            if idx >= 0:
                self.cmb_plantilla.blockSignals(True)
                self.cmb_plantilla.setCurrentIndex(idx)
                self.cmb_plantilla.blockSignals(False)
        geometria = datos.get("geometria")
        if geometria:
            try:
                self.restoreGeometry(QByteArray.fromHex(geometria.encode("ascii")))
            except Exception:
                pass
        sizes = datos.get("splitter")
        if isinstance(sizes, list) and len(sizes) == 2:
            self.splitter.setSizes([int(s) for s in sizes])

    def _guardar_ajustes(self, carpeta: Path) -> None:
        self._carpeta_destino = str(carpeta)
        self._actualizar_ajustes(
            plantilla=self.cmb_plantilla.currentData(),
            ultima_carpeta=str(carpeta),
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._guardar_borrador_ahora()
        self._actualizar_ajustes(
            plantilla=self.cmb_plantilla.currentData(),
            geometria=bytes(self.saveGeometry().toHex()).decode("ascii"),
            splitter=self.splitter.sizes(),
        )
        if self._instalar_al_cerrar and self._ruta_update_lista:
            try:
                iniciar_instalador(self._ruta_update_lista)
                self._instalar_al_cerrar = False
            except Exception:
                logger.exception("No se pudo iniciar la actualización preparada al cerrar")
        super().closeEvent(event)
