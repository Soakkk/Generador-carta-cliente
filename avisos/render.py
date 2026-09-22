"""Composicion y render del aviso (vista previa e impresion a PDF).

El contenido editable (titulo + cuerpo) se maneja como un unico documento
HTML que se dibuja entre la cabecera (logo + linea dorada) y el pie de
pagina fijo. Asi el usuario puede editarlo libremente (estilo Word) y lo
que se ve es lo que sale en el PDF.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QImage, QPageLayout, QPageSize, QPainter,
    QTextCursor, QTextDocument,
)
from PySide6.QtPrintSupport import QPrinter

from . import config
from . import estilo as E
from .templates import Contexto, Plantilla, render_cuerpo, render_titulo

# A4 en mm
A4_W_MM, A4_H_MM = 210.0, 297.0
# Margenes (mm)
MARGEN_X = 18.0
MARGEN_SUP = 13.0
MARGEN_INF = 16.0

# Tamanos del titulo y el pie como diferencia respecto al tamano de cuerpo
# (configurable), para que todo escale de forma proporcional.
DELTA_TITULO = 3.5
DELTA_PIE_NEGRITA = -2.0
DELTA_PIE_NORMAL = -2.5

def _mm(px_per_mm: float, mm: float) -> float:
    return mm * px_per_mm


def stylesheet(est: E.Estilo) -> str:
    return (
        f"p{{color:{config.INK};line-height:{est.interlineado}%;"
        f"margin:{est.espacio_parrafo}pt 0;text-align:justify;}}"
        f"li{{color:{config.INK};margin:1pt 0;text-align:left;}}"
        f"b{{color:{config.GREEN_SOFT};}}"
    )


def componer_documento(titulo: str, cuerpo_html: str, est: E.Estilo) -> str:
    """Une el titulo (como parrafo destacado) y el cuerpo en un unico HTML
    editable. Es el contenido inicial que se carga en el editor."""
    title_pt = est.tamano_cuerpo + DELTA_TITULO
    titulo_html = (
        f'<p align="center" style="font-size:{title_pt:.1f}pt;font-weight:bold;'
        f'color:{config.GREEN};text-align:center;margin-bottom:11pt;">{escape(titulo)}</p>'
    )
    return titulo_html + cuerpo_html


_PT_A_PX = 96.0 / 72.0  # 1 pt en pixeles logicos (referencia 96 DPI)


def aplicar_margenes_bloques(doc: QTextDocument, est: E.Estilo) -> None:
    """Aplica el espacio entre parrafos como margen real de cada bloque.

    QTextEdit ignora el `margin` del stylesheet (deja los parrafos pegados),
    asi que hay que fijarlo por codigo para que el EDITOR muestre el mismo
    espaciado que el PDF y sea de verdad WYSIWYG."""
    espacio = est.espacio_parrafo * _PT_A_PX
    titulo_gap = 11.0 * _PT_A_PX
    primero_visto = False
    prev_lista = False
    block = doc.begin()
    while block.isValid():
        if block.textList() is None:
            bf = block.blockFormat()
            # Deja aire tras una lista dando margen superior al parrafo siguiente.
            bf.setTopMargin(espacio if prev_lista else 0)
            bf.setBottomMargin(titulo_gap if not primero_visto else espacio)
            cur = QTextCursor(block)
            cur.mergeBlockFormat(bf)
            prev_lista = False
        else:
            prev_lista = True
        if block.text().strip():
            primero_visto = True
        block = block.next()


def documento_inicial(ctx: Contexto, plantilla: Plantilla,
                      est: E.Estilo | None = None) -> str:
    """Contenido HTML editable inicial (texto predefinido ya resuelto con
    los datos del formulario), para cargarlo en el editor."""
    est = est or E.cargar()
    return componer_documento(render_titulo(ctx, plantilla), render_cuerpo(ctx, plantilla), est)


def _doc_desde_html(html: str, ancho_px: float, est: E.Estilo,
                    dispositivo=None) -> QTextDocument:
    doc = QTextDocument()
    # Asociar el dispositivo antes de medir evita componer el texto a 96 DPI
    # y ampliarlo después. Así Qt calcula glifos, kerning y saltos de línea a
    # la resolución real de la imagen o del PDF, sin espacios irregulares.
    if dispositivo is not None:
        doc.documentLayout().setPaintDevice(dispositivo)
    doc.setDocumentMargin(0)
    f = QFont(est.fuente)
    f.setPointSizeF(est.tamano_cuerpo)
    doc.setDefaultFont(f)
    doc.setDefaultStyleSheet(stylesheet(est))
    doc.setTextWidth(ancho_px)
    doc.setHtml(html)
    return doc


def pintar_documento(painter: QPainter, ancho_px: float, alto_px: float,
                     res_dpi: float, contenido_html: str,
                     info: dict | None = None, est: E.Estilo | None = None) -> None:
    """Dibuja logo + linea dorada + `contenido_html` (titulo y cuerpo ya
    juntos) + pie de pagina fijo. `contenido_html` puede venir del editor."""
    est = est or E.cargar()
    ppm = res_dpi / 25.4
    fuente = est.fuente

    x0 = _mm(ppm, MARGEN_X)
    content_w = ancho_px - 2 * x0
    y = _mm(ppm, MARGEN_SUP)

    painter.fillRect(QRectF(0, 0, ancho_px, alto_px), QColor("#FFFFFF"))

    # --- Logo (centrado) ---
    logo = QImage(str(config.logo_path()))
    if not logo.isNull():
        target_w = content_w * 0.48
        escala = logo.scaledToWidth(int(target_w), Qt.SmoothTransformation)
        lx = (ancho_px - escala.width()) / 2.0
        painter.drawImage(QRectF(lx, y, escala.width(), escala.height()), escala)
        y += escala.height() + _mm(ppm, 3)

    # --- Linea dorada ---
    painter.fillRect(QRectF(x0, y, content_w, _mm(ppm, 0.7)), QColor(config.GOLD))
    y += _mm(ppm, 5)

    # --- Pie de pagina: se calcula antes para saber el hueco disponible ---
    pie_y = alto_px - _mm(ppm, MARGEN_INF) - _mm(ppm, 13)

    # --- Contenido: maquetado directamente a la resolucion del destino ---
    alto_disponible = max(pie_y - y, 1)
    doc = _doc_desde_html(contenido_html, content_w, est, painter.device())
    if info is not None:
        info["desborda"] = doc.size().height() > alto_disponible
    painter.save()
    painter.translate(x0, y)
    doc.drawContents(painter, QRectF(0, 0, content_w, alto_disponible))
    painter.restore()

    # --- Pie de pagina ---
    painter.fillRect(QRectF(x0, pie_y, content_w, _mm(ppm, 0.5)), QColor(config.GOLD))
    pie_y += _mm(ppm, 2.5)

    fp_bold = QFont(fuente)
    fp_bold.setPointSizeF(est.tamano_cuerpo + DELTA_PIE_NEGRITA)
    fp_bold.setBold(True)
    fp = QFont(fuente)
    fp.setPointSizeF(est.tamano_cuerpo + DELTA_PIE_NORMAL)
    painter.setPen(QColor(config.GREEN))

    lineas = [
        (fp_bold, config.COMPANY_TITULARES),
        (fp, f"{config.COMPANY_DIRECCION} · {config.COMPANY_TELEFONOS}"),
        (fp, config.COMPANY_EMAIL),
    ]
    for fuente_linea, texto in lineas:
        painter.setFont(fuente_linea)
        r = QRectF(x0, pie_y, content_w, _mm(ppm, 5))
        painter.drawText(r, int(Qt.AlignHCenter | Qt.AlignTop), texto)
        pie_y += _mm(ppm, 4.2)


# --- Render a imagen (vista previa) --------------------------------------
def render_preview_documento(contenido_html: str, dpi: float = 110.0,
                             info: dict | None = None, est: E.Estilo | None = None) -> QImage:
    ppm = dpi / 25.4
    w = int(round(A4_W_MM * ppm))
    h = int(round(A4_H_MM * ppm))
    img = QImage(w, h, QImage.Format_RGB32)
    dpm = int(round(dpi / 0.0254))
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    try:
        pintar_documento(p, w, h, dpi, contenido_html, info=info, est=est)
    finally:
        p.end()
    return img


def render_preview_textos(titulo: str, cuerpo_html: str, dpi: float = 110.0,
                          info: dict | None = None, est: E.Estilo | None = None) -> QImage:
    est = est or E.cargar()
    contenido = componer_documento(titulo, cuerpo_html, est)
    return render_preview_documento(contenido, dpi=dpi, info=info, est=est)


def render_preview(ctx: Contexto, plantilla: Plantilla, dpi: float = 110.0,
                   info: dict | None = None, est: E.Estilo | None = None) -> QImage:
    titulo = render_titulo(ctx, plantilla)
    cuerpo_html = render_cuerpo(ctx, plantilla)
    return render_preview_textos(titulo, cuerpo_html, dpi=dpi, info=info, est=est)


# --- Render a PDF --------------------------------------------------------
def _nuevo_printer(ruta: str | Path) -> QPrinter:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(ruta))
    printer.setPageSize(QPageSize(QPageSize.A4))
    printer.setFullPage(True)
    printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
    return printer


def render_pdf_documento(contenido_html: str, ruta: str | Path,
                         info: dict | None = None, est: E.Estilo | None = None) -> None:
    printer = _nuevo_printer(ruta)
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("No se pudo iniciar la impresion a PDF")
    try:
        res = printer.resolution()
        page = printer.pageRect(QPrinter.DevicePixel)
        pintar_documento(painter, page.width(), page.height(), res, contenido_html,
                         info=info, est=est)
    finally:
        painter.end()


def render_pdf(ctx: Contexto, plantilla: Plantilla, ruta: str | Path,
               info: dict | None = None, est: E.Estilo | None = None) -> None:
    """Genera el PDF directamente desde la plantilla (usado en el lote)."""
    est = est or E.cargar()
    titulo = render_titulo(ctx, plantilla)
    cuerpo_html = render_cuerpo(ctx, plantilla)
    contenido = componer_documento(titulo, cuerpo_html, est)
    render_pdf_documento(contenido, ruta, info=info, est=est)


def render_pdf_plantilla_texto(ctx: Contexto, titulo_tpl: str, cuerpo_tpl: str,
                               ruta: str | Path, info: dict | None = None,
                               est: E.Estilo | None = None) -> None:
    """Genera un PDF desde una instantanea editable de titulo y cuerpo.

    Se usa en la generacion por lotes para conservar los cambios manuales del
    editor y sustituir, aun asi, cliente, periodo, fecha y documentos en cada
    copia individual.
    """
    from .templates import render_cuerpo_texto, render_titulo_texto

    est = est or E.cargar()
    titulo = render_titulo_texto(ctx, titulo_tpl)
    cuerpo_html = render_cuerpo_texto(ctx, cuerpo_tpl)
    render_pdf_documento(componer_documento(titulo, cuerpo_html, est), ruta,
                         info=info, est=est)


# ======================================================================
#  Re-templatizacion: convertir el texto editado en el editor de vuelta a
#  una plantilla (con placeholders), para "Guardar como predeterminado".
# ======================================================================
def _wrap_negrita(t: str) -> str:
    """Envuelve el nucleo (sin espacios de los extremos) en *...*."""
    core = t.strip()
    if not core:
        return t
    izq = len(t) - len(t.lstrip())
    der = len(t) - len(t.rstrip())
    return t[:izq] + "*" + core + "*" + (t[len(t) - der:] if der else "")


def _reverse_scalars(texto: str, ctx: Contexto) -> str:
    """Sustituye los valores concretos (cliente, fecha, periodo, ano) por
    sus placeholders, para que el texto guardado se rellene solo cada vez."""
    # Saludo: "Estimado/a <lo que sea>:" -> "Estimado/a {cliente}:"
    texto = re.sub(r"(Estimad[oa]/a\s+)([^\n:]{0,80}?)(\s*:)",
                   r"\1{cliente}\3", texto, count=1)
    pares = [
        (ctx.fecha_limite_txt, "{fecha_limite}"),
        (ctx.periodo_largo, "{periodo}"),
        (str(ctx.anio), "{anio}"),
    ]
    if ctx.cliente.strip():
        pares.append((ctx.cliente.strip(), "{cliente}"))
    for viejo, nuevo in sorted(pares, key=lambda p: len(p[0]), reverse=True):
        if viejo:
            texto = texto.replace(viejo, nuevo)
    return texto


def _bloque_a_texto(block) -> str:
    """Texto de un parrafo con la negrita reconvertida a *...*."""
    partes: list[str] = []
    it = block.begin()
    while not it.atEnd():
        frag = it.fragment()
        if frag.isValid():
            t = frag.text()
            if t.strip() and frag.charFormat().fontWeight() > QFont.Normal:
                partes.append(_wrap_negrita(t))
            else:
                partes.append(t)
        it += 1
    unido = "".join(partes)
    return unido if unido.strip() else block.text()


def documento_a_plantilla(doc: QTextDocument, ctx: Contexto) -> tuple[str, str]:
    """Convierte el contenido editado en (titulo_tpl, cuerpo_tpl) con
    placeholders. Las listas -> {documentos}, las tablas -> {tabla_plazos}."""
    rangos_tabla = [(fr.firstPosition(), fr.lastPosition())
                    for fr in doc.rootFrame().childFrames()]

    def en_tabla(pos: int) -> bool:
        return any(a <= pos <= b for a, b in rangos_tabla)

    titulo = ""
    cuerpo: list[str] = []
    primer = True
    tabla_emitida = False
    documentos_emitido = False

    block = doc.begin()
    while block.isValid():
        texto = block.text().strip()
        if en_tabla(block.position()):
            if not tabla_emitida:
                cuerpo.append("{tabla_plazos}")
                tabla_emitida = True
            block = block.next()
            continue
        if block.textList() is not None:
            # Cualquier lista (la base de documentos, o la de un bloque de
            # documentacion opcional activo) se representa con un unico
            # {documentos}: ese placeholder es dinamico y ya incluye la
            # documentacion opcional que este marcada en cada momento, asi
            # que no hace falta (ni se puede) guardar el texto de una
            # segunda lista de forma literal.
            if not documentos_emitido:
                cuerpo.append("{documentos}")
                documentos_emitido = True
            block = block.next()
            continue
        if primer:
            if texto:
                titulo = _reverse_scalars(texto, ctx)
                primer = False
            block = block.next()
            continue
        if texto:
            cuerpo.append(_reverse_scalars(_bloque_a_texto(block), ctx))
        block = block.next()

    return titulo, "\n\n".join(cuerpo)
