import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import tempfile
from pathlib import Path

# Permite ejecutar este archivo directamente desde la raíz del repositorio,
# tal y como indican README y el plan de release, sin depender de PYTHONPATH.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Aislar la config del usuario real durante el test
tmp_cfg = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp_cfg)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

app = QApplication([])

from avisos import clients as C
from avisos import estilo as EST
from avisos import extras as X
from avisos import history as H
from avisos import render as R
from avisos import templates as T
from avisos.app import MainWindow
from avisos.ui.clientes import ClientesDialog, EditorClienteDialog
from avisos.ui.extras import ExtrasDialog
from avisos.ui.formato import FormatoDialog
from avisos.ui.historial import HistorialDialog
from avisos.ui.lote import LoteDialog
from avisos.ui.plantillas import PlantillaEditorDialog

errores = []

def check(nombre, cond):
    estado = "OK " if cond else "FALLO"
    print(f"[{estado}] {nombre}")
    if not cond:
        errores.append(nombre)

# --- clientes ---
clientes = C.cargar()
check("clientes vacio al inicio", clientes == [])
clientes = C.upsert(clientes, C.Cliente(nombre="Juan Pérez García", nif="12345678A", telefono="600111222", email="juan@example.com"))
clientes = C.upsert(clientes, C.Cliente(nombre="Ana López"))
C.guardar(clientes)
clientes2 = C.cargar()
check("clientes se guardan y recargan (2)", len(clientes2) == 2)
check("buscar cliente por nombre", C.buscar(clientes2, "juan pérez garcía") is not None)

# --- historial ---
H.registrar("Solicitud de documentación — Trimestre", "1T", 2026, "Juan Pérez García",
            r"C:\tmp\aviso.pdf", plantilla_id="solicitud_trim",
            documentos=["Factura de prueba"], notas="Nota guardada")
hist = H.cargar()
check("historial registra entradas", len(hist) == 1)
check("historial conserva datos para reutilizar el aviso",
      hist[0].plantilla_id == "solicitud_trim" and hist[0].documentos == ["Factura de prueba"])

# --- overrides de plantillas ---
p = T.PLANTILLAS[0]
check("sin override al inicio", not T.tiene_override(p.id))
T.guardar_override(p.id, "TITULO PERSONALIZADO {anio}", "Estimado/a {cliente}:\n\nTexto de prueba *importante*.")
check("override guardado", T.tiene_override(p.id))
ctx_prueba = T.Contexto(periodo="1T", anio=2026, cliente="Juan Pérez García")
titulo = T.render_titulo(ctx_prueba, p)
check("override se usa en render_titulo", titulo == "TITULO PERSONALIZADO 2026")
cuerpo = T.render_cuerpo(ctx_prueba, p)
check("negrita en override", "<b>importante</b>" in cuerpo)
T.restablecer_override(p.id)
check("restablecer quita el override", not T.tiene_override(p.id))
check("tras restablecer, vuelve al texto de fabrica", T.render_titulo(ctx_prueba, p) != "TITULO PERSONALIZADO 2026")

# --- aviso de fecha ---
import datetime
check("sabado detectado", T.aviso_fecha(datetime.date(2026, 4, 18)) != "")  # 18 abril 2026 es sabado
check("martes no genera aviso (no es finde ni festivo fijo)", T.aviso_fecha(datetime.date(2026, 4, 21)) == "")

# --- render con nif automatico ---
valores = T._valores_comunes(T.Contexto(cliente="Juan Pérez García"))
check("nif se autocompleta desde la base de clientes", valores["nif"] == "12345678A")

# --- MainWindow arranca sin errores ---
win = MainWindow()
win._comprobacion_inicial_hecha = True  # sin red ni hilos de actualizacion en tests
win.resize(1360, 880)
win.show()
app.processEvents()
win._actualizar_preview()
app.processEvents()
check("MainWindow crea preview", win.preview.label.pixmap() is not None)
check("el flujo diario abre directamente en el texto", win.paginas_documento.currentIndex() == 1)
win._copiar_texto()
check("copiar texto usa contenido plano", "documentación" in QApplication.clipboard().text()
      and "<" not in QApplication.clipboard().text())

# --- la rueda desplaza la pantalla, no cambia controles por accidente ---
class _RuedaFalsa:
    def __init__(self):
        self.ignorada = False
    def ignore(self):
        self.ignorada = True

anio_antes = win.spin_anio.value()
evento_rueda = _RuedaFalsa()
win.spin_anio.wheelEvent(evento_rueda)
check("la rueda no cambia el año", win.spin_anio.value() == anio_antes and evento_rueda.ignorada)
plantilla_antes = win.cmb_plantilla.currentIndex()
evento_combo = _RuedaFalsa()
win.cmb_plantilla.wheelEvent(evento_combo)
check("la rueda no cambia la plantilla",
      win.cmb_plantilla.currentIndex() == plantilla_antes and evento_combo.ignorada)

# --- editor tipo Word: contenido inicial, dirty y regeneracion ---
check("el editor arranca con el texto predefinido", "documentación" in win.editor.toPlainText())
check("el editor no esta 'dirty' al arrancar", win._editor_dirty is False)
# simular edicion a mano
win.editor.setFocus()
win.editor.textCursor().insertText("XYZ_EDICION_MANUAL ")
app.processEvents()
check("editar a mano marca el editor como modificado", win._editor_dirty is True)
# cambiar un dato del formulario NO debe pisar la edicion manual (solo avisa)
win.txt_cliente.setText("Cliente De Prueba")
app.processEvents()
check("cambiar datos con texto editado no pisa el texto (muestra banner)",
      "XYZ_EDICION_MANUAL" in win.editor.toPlainText() and not win.banner_datos.isHidden()
      and "pendientes" in win.lbl_estado.text())
# restaurar/regenerar descarta la edicion y aplica los datos
win._regenerar_editor()
app.processEvents()
check("regenerar aplica el nombre del cliente al texto",
      "Cliente De Prueba" in win.editor.toPlainText())
check("regenerar quita la edicion manual", "XYZ_EDICION_MANUAL" not in win.editor.toPlainText())
check("tras regenerar, el editor deja de estar modificado", win._editor_dirty is False)
# el PDF se genera desde el contenido del editor (con una marca manual)
win.editor.textCursor().insertText("MARCA_EN_PDF ")
app.processEvents()
import tempfile as _tf
pdf_editor = str(Path(_tf.mkdtemp()) / "editor.pdf")
from avisos.render import render_pdf_documento as _render_pdf_doc
_render_pdf_doc(win.editor.toHtml(), pdf_editor)
check("el PDF desde el editor se genera", os.path.getsize(pdf_editor) > 1000)
win._regenerar_editor()  # dejar limpio para el resto del test

# --- documentacion opcional: guardar, marcar/desmarcar, persistencia ---
check("no hay documentacion opcional al inicio", X.cargar() == [])
extras_lista = X.upsert([], X.Extra(etiqueta="Venta de bienes", intro="En caso de venta:",
                                    lineas=["Escritura de venta.", "Justificante de gastos."]))
X.guardar(extras_lista)
check("la documentacion opcional se guarda y recarga", len(X.cargar()) == 1)

win._refrescar_lista_extras()
check("la etiqueta opcional aparece en el formulario", "Venta de bienes" in win._extra_buttons)
item_extra = win._extra_buttons["Venta de bienes"]
check("la etiqueta opcional arranca desmarcada", not item_extra.isChecked())
check("la lista base no se toca al marcar un bloque opcional",
      "Escritura de venta." not in "\n".join(win._documentos_actuales()))

item_extra.setChecked(True)
app.processEvents()
check("marcar el checkbox NO anade las lineas a la lista base de documentos",
      "Escritura de venta." not in "\n".join(win._documentos_actuales()))
check("marcar el checkbox aparece como bloque propio en el editor (no dirty)",
      "Escritura de venta." in win.editor.toPlainText())
check("la frase introductoria tambien aparece", "En caso de venta:" in win.editor.toPlainText())
check("_contexto() recoge el extra marcado", len(win._contexto().documentos_extra) == 1)

# el bloque debe ser una lista APARTE de la base (parrafo/lista propios, no
# mezclado en la misma vineta) -> comprobar via el HTML generado
ctx_extra = win._contexto()
cuerpo_html_extra = T.render_cuerpo(ctx_extra, win._plantilla_actual())
check("el bloque opcional genera su propia lista <ul> (dos <ul> en total)",
      cuerpo_html_extra.count("<ul") == 2)

item_extra.setChecked(False)
app.processEvents()
check("desmarcar el checkbox quita el bloque del editor",
      "Escritura de venta." not in win.editor.toPlainText())
check("_contexto() ya no incluye el extra", len(win._contexto().documentos_extra) == 0)

# restablecer la lista de documentos desmarca los checkboxes
item_extra.setChecked(True)
app.processEvents()
win._reset_docs()
app.processEvents()
check("restablecer la lista desmarca los checkboxes de opcionales",
      not win._extra_buttons["Venta de bienes"].isChecked())

# "Guardar como predeterminado" con un extra marcado no debe duplicar {documentos}
item_extra.setChecked(True)
app.processEvents()
_tit_extra, _cue_extra = R.documento_a_plantilla(win.editor.document(), win._contexto())
check("guardar con un extra marcado no duplica el placeholder {documentos}",
      _cue_extra.count("{documentos}") == 1)
item_extra.setChecked(False)
app.processEvents()

dlg_extras = ExtrasDialog(win)
check("ExtrasDialog se construye", dlg_extras.tabla.rowCount() == 1)
dlg_extras.close()

# --- dialogos se instancian sin fallar ---
dlg_clientes = ClientesDialog(win)
check("ClientesDialog se construye", dlg_clientes.tabla.rowCount() == 2)
dlg_clientes.close()

dlg_hist = HistorialDialog(win)
check("HistorialDialog se construye", dlg_hist.tabla.rowCount() == 1)
dlg_hist.close()
win._reutilizar_historial(hist[0])
app.processEvents()
check("crear otro igual recupera documentos y notas del historial",
      win._documentos_actuales() == ["Factura de prueba"]
      and win.gb_notas.isChecked() and win.txt_notas.toPlainText() == "Nota guardada")
win.gb_notas.setChecked(False)
win.txt_notas.clear()
win._set_docs(win._plantilla_actual().documentos_def)
win.txt_cliente.clear()
win._aplicar_periodo_sugerido()
win._regenerar_editor()

dlg_editor = PlantillaEditorDialog(win)
app.processEvents()
check("PlantillaEditorDialog previsualiza", dlg_editor.preview.label.pixmap() is not None)
dlg_editor.close()

carpeta_lote = tempfile.mkdtemp()
from PySide6.QtGui import QTextCursor
win.editor.moveCursor(QTextCursor.End)
win.editor.textCursor().insertText(" CAMBIO_COMUN_LOTE")
tpl_lote = R.documento_a_plantilla(win.editor.document(), win._contexto())
check("el lote captura las ediciones manuales del documento actual",
      "CAMBIO_COMUN_LOTE" in tpl_lote[1])
dlg_lote = LoteDialog(win, win._contexto(), win._plantilla_actual(), carpeta_lote,
                      documento_tpl=tpl_lote)
from PySide6.QtCore import Qt as QtC
for i in range(dlg_lote.lista.count()):
    dlg_lote.lista.item(i).setCheckState(QtC.Checked)
dlg_lote._carpeta = carpeta_lote
nombres = dlg_lote._nombres_elegidos()
check("lote detecta los 2 clientes marcados", len(nombres) == 2)

# Generar directamente sin pasar por QMessageBox (llamamos a la logica manualmente)
from dataclasses import replace
from avisos.render import render_pdf_plantilla_texto as _render_pdf_lote
from avisos.util import nombre_archivo as _nombre_archivo
generados = 0
for nombre in nombres:
    ctx = replace(win._contexto(), cliente=nombre)
    ruta = Path(carpeta_lote) / _nombre_archivo(win._plantilla_actual(), ctx)
    _render_pdf_lote(ctx, *tpl_lote, ruta)
    if ruta.exists():
        generados += 1
check("lote genera un PDF por cliente", generados == 2)
win._regenerar_editor()

# --- version en el titulo ---
from avisos import __version__ as _version
check("titulo incluye la version", f"v{_version}" in win.windowTitle())

# --- periodo/anio sugerido segun fecha del sistema ---
clave_esperada, anio_esperado = T.periodo_sugerido_hoy()
check("selector de periodo aplica el sugerido al abrir",
      win._periodo_actual() == clave_esperada or win._plantilla_actual().id == "cierre_anual")

# --- desplegables no cortan texto (popup mas ancho que el texto mas largo) ---
ancho_max_texto = max(win.cmb_plantilla.fontMetrics().horizontalAdvance(win.cmb_plantilla.itemText(i))
                      for i in range(win.cmb_plantilla.count()))
check("popup del combo de plantillas es mas ancho que el texto",
      win.cmb_plantilla.view().minimumWidth() >= ancho_max_texto)

# --- splitter presente (separador arrastrable) ---
from PySide6.QtWidgets import QSplitter
splitters = win.centralWidget().findChildren(QSplitter)
check("hay un QSplitter en la ventana principal", len(splitters) == 1)

# --- calculo de plazos AEAT ---
import datetime as _dt
d_general = T.fecha_general_periodo("1T", 2026)
d_domicilio = T.fecha_domiciliacion_periodo("1T", 2026)
check("domiciliacion 1T 2026 son 3 dias habiles antes (aqui coincide con 5 naturales)",
      (d_general - d_domicilio).days == 5)
check("fecha general nunca cae en sabado/domingo/festivo",
      d_general.weekday() < 5 and not T.es_festivo(d_general))
check("plazo_por_defecto usa la domiciliacion", T.plazo_por_defecto("1T", 2026) == d_domicilio)

# --- 4T vence el dia 30 de enero (no el 20), verificado contra el calendario oficial AEAT ---
d_general_4t = T.fecha_general_periodo("4T", 2025)   # 4T de 2025 se presenta en enero de 2026
d_domicilio_4t = T.fecha_domiciliacion_periodo("4T", 2025)
check("4T vence el 30 de enero (oficial AEAT 2026)", d_general_4t == _dt.date(2026, 1, 30))
check("domiciliacion 4T enero 2026 es el 27 (oficial AEAT: 3 dias habiles, sin fin de semana de por medio)",
      d_domicilio_4t == _dt.date(2026, 1, 27))

# --- regresion critica: el tamano de letra debe escalar con el DPI real ---
# (antes, el cuerpo del texto salia correcto en la vista previa pero
# minusculo en el PDF real, porque QTextDocument asume 96 DPI internamente
# y el QPrinter imprime a 1200 DPI; ver avisos/render.py _QTEXTDOCUMENT_DPI)
from avisos.render import render_preview as _render_preview_test

def _extension_vertical_texto(img):
    w, h = img.width(), img.height()
    filas = 0
    for y in range(int(h * 0.24), int(h * 0.55)):
        for x in range(0, w, 4):
            c = img.pixelColor(x, y)
            if c.red() < 200 or c.green() < 200 or c.blue() < 200:
                filas += 1
                break
    return filas

ctx_dpi = T.Contexto(periodo="1T", anio=2026, cliente="Juan Pérez",
                     documentos=T.PLANTILLAS[0].documentos_def)
filas_96 = _extension_vertical_texto(_render_preview_test(ctx_dpi, T.PLANTILLAS[0], dpi=96))
filas_600 = _extension_vertical_texto(_render_preview_test(ctx_dpi, T.PLANTILLAS[0], dpi=600))
ratio = (filas_600 / filas_96) if filas_96 else 0
check(f"el texto escala con el DPI real (96dpi={filas_96} filas, 600dpi={filas_600} filas, ratio={ratio:.1f}~6.25)",
      5.0 <= ratio <= 8.0)

# --- "Guardar como predeterminado": round-trip editor -> plantilla ---
from PySide6.QtGui import QTextDocument as _QTD
from avisos.render import documento_inicial as _doc_ini, stylesheet as _ss, documento_a_plantilla as _a_tpl
for _p in T.PLANTILLAS:
    T.restablecer_override(_p.id)
    _periodo = "4T" if _p.id == "cierre_anual" else "1T"
    _ctx = T.Contexto(periodo=_periodo, anio=2026, cliente="Juan Pérez García",
                      documentos=_p.documentos_def, navidad=False)
    _html = _doc_ini(_ctx, _p, EST.Estilo())
    _doc = _QTD()
    _doc.setDefaultStyleSheet(_ss(EST.Estilo()))
    _doc.setHtml(_html)
    _tit, _cue = _a_tpl(_doc, _ctx)
    check(f"[{_p.id}] re-templatiza el titulo con placeholders",
          "{anio}" in _tit or "{periodo}" in _tit)
    check(f"[{_p.id}] el cuerpo recupera el placeholder de cliente", "{cliente}" in _cue)
    check(f"[{_p.id}] el cuerpo recupera la lista de documentos", "{documentos}" in _cue)
    # guardar como override y comprobar que se rellena con OTRO cliente
    T.guardar_override(_p.id, _tit, _cue)
    _ctx2 = T.Contexto(periodo=_periodo, anio=2027, cliente="Otra Persona SL",
                       documentos=_p.documentos_def, navidad=False)
    _resuelto = T.render_cuerpo(_ctx2, _p)
    check(f"[{_p.id}] el override guardado se rellena con el nuevo cliente/ano",
          "Otra Persona SL" in _resuelto and "2027" in _resuelto and "Juan Pérez" not in _resuelto)
    T.restablecer_override(_p.id)

# recordatorio: la tabla de plazos debe convertirse en su placeholder
_rec = T.por_id("recordatorio")
_ctx_rec = T.Contexto(periodo="1T", anio=2026, documentos=_rec.documentos_def)
_doc_rec = _QTD()
_doc_rec.setDefaultStyleSheet(_ss(EST.Estilo()))
_doc_rec.setHtml(_doc_ini(_ctx_rec, _rec, EST.Estilo()))
_tit_rec, _cue_rec = _a_tpl(_doc_rec, _ctx_rec)
check("recordatorio recupera la tabla de plazos", "{tabla_plazos}" in _cue_rec)

# --- formato configurable (fuente/tamano/interlineado/espacio) ---
check("estilo por defecto es Georgia 11pt", EST.cargar() == EST.Estilo())
est_grande = EST.Estilo(fuente="Georgia", tamano_cuerpo=14.0, interlineado=150.0, espacio_parrafo=12.0)
EST.guardar(est_grande)
check("estilo se guarda y recarga", EST.cargar() == est_grande)

filas_chico = _extension_vertical_texto(
    _render_preview_test(ctx_dpi, T.PLANTILLAS[0], dpi=150, est=EST.Estilo(tamano_cuerpo=9.0)))
filas_grande = _extension_vertical_texto(
    _render_preview_test(ctx_dpi, T.PLANTILLAS[0], dpi=150, est=EST.Estilo(tamano_cuerpo=14.0)))
check(f"un tamano de letra mayor ocupa mas espacio vertical ({filas_chico} -> {filas_grande})",
      filas_grande > filas_chico)

est_restablecido = EST.restablecer()
check("restablecer vuelve a los valores de fabrica", est_restablecido == EST.Estilo())

dlg_formato = FormatoDialog(win)
app.processEvents()
check("FormatoDialog previsualiza", dlg_formato.preview.label.pixmap() is not None)
tamano_antes = dlg_formato.spin_tamano.value()
evento_formato = _RuedaFalsa()
dlg_formato.spin_tamano.wheelEvent(evento_formato)
check("la rueda no cambia el tamaño de letra",
      dlg_formato.spin_tamano.value() == tamano_antes and evento_formato.ignorada)
dlg_formato.close()

# --- utilidades: nombre de archivo sin colision ---
from avisos.util import ruta_sin_colision
carpeta_tmp = Path(tempfile.mkdtemp())
(carpeta_tmp / "prueba.pdf").write_text("x")
ruta_libre = ruta_sin_colision(carpeta_tmp, "prueba.pdf")
check("ruta_sin_colision evita sobrescribir", ruta_libre.name == "prueba (2).pdf")

# --- auto-registro de clientes ---
check("asegurar_cliente anade un cliente nuevo", C.asegurar_cliente("Cliente Nuevo De Prueba") is True)
check("asegurar_cliente no duplica uno existente", C.asegurar_cliente("Cliente Nuevo De Prueba") is False)

# --- updater: logica pura sin red ---
from avisos import updater as U
check("version_tupla compara correctamente", U._version_tupla("v1.2.0") > U._version_tupla("v1.1.0"))
remota_falsa = U.VersionRemota(
    tag="v1.2.0", version=(1, 2, 0), url_instalador="http://x",
    url_sha256="http://x.sha256", notas="")
check("hay_actualizacion detecta version mas nueva", U.hay_actualizacion("1.1.0", remota_falsa) is True)
check("hay_actualizacion no marca la misma version", U.hay_actualizacion("1.2.0", remota_falsa) is False)

# --- escritura atomica de JSON ---
from avisos import config as CFG
ruta_json = Path(tempfile.mkdtemp()) / "atomico.json"
CFG.escribir_json(ruta_json, {"a": 1, "acentos": "áéñ"})
check("escribir_json escribe y leer_json recupera",
      CFG.leer_json(ruta_json, None) == {"a": 1, "acentos": "áéñ"})
check("escribir_json no deja archivo temporal",
      not ruta_json.with_suffix(".json.tmp").exists())
check("leer_json devuelve el valor por defecto si no existe",
      CFG.leer_json(ruta_json.parent / "no_existe.json", "def") == "def")
ruta_json.write_text("{corrupto", "utf-8")
check("leer_json tolera un archivo corrupto", CFG.leer_json(ruta_json, {}) == {})

# --- log: configurar y excepthook no rompen ---
from avisos import log as LOG
LOG.configurar()
LOG.logger.info("linea de prueba desde test_full")
check("el archivo de log existe tras configurar", LOG.ruta_log().exists())
LOG.instalar_excepthook()
check("el excepthook queda instalado", sys.excepthook is not sys.__excepthook__)

if errores:
    print(f"\n{len(errores)} FALLO(S): {errores}")
    sys.exit(1)
print("\nTODO OK")
