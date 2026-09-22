"""Plantillas de avisos, motor de sustitucion y overrides editables.

Cada plantilla tiene un texto de titulo y un texto de cuerpo (plano, con
parrafos separados por una linea en blanco) que puede contener:

- Placeholders entre llaves: {cliente} {periodo} {anio} {fecha_limite}
  {nif} {documentos} {notas} {felicitacion_navidad} {tabla_plazos}
- Negrita al estilo WhatsApp: *texto en negrita*

Los placeholders {documentos}, {notas}, {tabla_plazos} y
{felicitacion_navidad} deben ir solos en su propio parrafo: si su valor
queda vacio (p. ej. no hay notas, o no se marco la felicitacion), el
parrafo entero desaparece del aviso.

El texto "de fabrica" de cada plantilla vive en este fichero. El usuario
puede sobrescribirlo desde el editor de plantillas de la aplicacion; esas
sobrescrituras se guardan en un JSON en la carpeta de configuracion y
tienen prioridad sobre el texto de fabrica.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import config

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Periodos disponibles: clave -> etiqueta larga, meses[0-based] y primer
# vencimiento general. En el 4T hay dos grupos de fechas: retenciones hasta
# el 20 de enero y modelos 130/131/303 hasta el 30. Para pedir documentacion
# de forma prudente usamos siempre el primer vencimiento; la tabla detallada
# muestra ambos.
PERIODOS = {
    "1T": {"largo": "1.er Trimestre", "corto": "1T", "meses": [0, 1, 2],
           "plazo": (4, 20), "anio_offset": 0},
    "2T": {"largo": "2.º Trimestre", "corto": "2T", "meses": [3, 4, 5],
           "plazo": (7, 20), "anio_offset": 0},
    "3T": {"largo": "3.er Trimestre", "corto": "3T", "meses": [6, 7, 8],
           "plazo": (10, 20), "anio_offset": 0},
    "4T": {"largo": "4.º Trimestre", "corto": "4T", "meses": [9, 10, 11],
           "plazo": (1, 20), "anio_offset": 1},
    "RENTA": {"largo": "Ejercicio (Renta)", "corto": "Renta", "meses": list(range(12)),
              "plazo": (6, 30), "anio_offset": 0},
}


def fecha_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


FESTIVOS_FIJOS = {
    (1, 1): "Año Nuevo", (1, 6): "Reyes", (5, 1): "Día del Trabajo",
    (8, 15): "Asunción", (10, 12): "Fiesta Nacional", (11, 1): "Todos los Santos",
    (12, 6): "Día de la Constitución", (12, 8): "Inmaculada", (12, 25): "Navidad",
}


def _viernes_santo(anio: int) -> date:
    """Domingo de Pascua (algoritmo de Gauss/Meeus) menos dos dias."""
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    domingo_pascua = date(anio, mes, dia)
    return domingo_pascua - timedelta(days=2)


def es_festivo(d: date) -> bool:
    """Festivos nacionales fijos + Viernes Santo.

    La propia AEAT considera inhabiles tambien los festivos autonomicos y
    locales, pero aqui solo se comprueban los nacionales fijos y el
    Viernes Santo (movil). Para fechas cercanas a un festivo regional de
    Murcia, conviene revisar el calendario oficial de la AEAT.
    """
    if (d.month, d.day) in FESTIVOS_FIJOS:
        return True
    return d == _viernes_santo(d.year)


def aviso_fecha(d: date) -> str:
    """Devuelve un aviso breve si la fecha cae en fin de semana o festivo, si no ''."""
    festivo = FESTIVOS_FIJOS.get((d.month, d.day))
    if festivo:
        return f"Cae en festivo ({festivo})."
    if d == _viernes_santo(d.year):
        return "Cae en festivo (Viernes Santo)."
    if d.weekday() >= 5:  # 5=sabado, 6=domingo
        return "Cae en fin de semana."
    return ""


def _siguiente_dia_habil(d: date) -> date:
    while d.weekday() >= 5 or es_festivo(d):
        d += timedelta(days=1)
    return d


def _restar_dias_habiles(d: date, n: int) -> date:
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5 and not es_festivo(d):
            n -= 1
    return d


def fecha_general_periodo(clave: str, anio: int) -> date:
    """Primer vencimiento general del periodo, ajustado al dia habil.

    Para el 4T devuelve el vencimiento de retenciones (20 de enero). Los
    modelos 130/131/303 tienen un segundo vencimiento al final de enero,
    disponible mediante ``fecha_general_cierre_tardio``.
    """
    info = PERIODOS[clave]
    mes, dia = info["plazo"]
    base = date(anio + info["anio_offset"], mes, dia)
    return _siguiente_dia_habil(base)


def fecha_domiciliacion_periodo(clave: str, anio: int) -> date:
    """Fecha limite para domiciliar el pago: 3 dias habiles antes de la
    fecha general (regla de la AEAT: minimo 3 dias habiles/5 naturales de
    separacion). No es un "-5 naturales" fijo: coincide con -5 cuando de
    por medio hay un fin de semana, pero da -3 cuando no lo hay (p. ej. en
    enero, si el dia 30 cae entre martes y viernes)."""
    if clave == "RENTA":
        return fecha_general_periodo(clave, anio)
    return _restar_dias_habiles(fecha_general_periodo(clave, anio), 3)


def fecha_general_cierre_tardio(anio: int) -> date:
    """Vencimiento del 4T para los modelos 130, 131, 303 y 309."""
    return _siguiente_dia_habil(date(anio + 1, 1, 30))


def fecha_domiciliacion_cierre_tardio(anio: int) -> date:
    """Fin de domiciliacion del segundo grupo de modelos del 4T."""
    return _restar_dias_habiles(fecha_general_cierre_tardio(anio), 3)


def plazo_por_defecto(clave: str, anio: int) -> date:
    """Fecha que se usa por defecto en los avisos: la de domiciliacion,
    porque la practica totalidad de los clientes domicilia el pago."""
    return fecha_domiciliacion_periodo(clave, anio)


def periodo_sugerido_hoy(hoy: date | None = None) -> tuple[str, int]:
    """Periodo y año mas probable segun la fecha actual del sistema.

    Los avisos de un trimestre se preparan y envian entre el mes
    siguiente al cierre del trimestre y su mes de presentacion, asi que
    se agrupan los meses del año alrededor de esas fechas de presentacion
    (abril->1T, julio->2T, octubre->3T, enero->4T).
    """
    hoy = hoy or date.today()
    mes = hoy.month
    if mes in (11, 12):
        return "4T", hoy.year
    if mes == 1:
        return "4T", hoy.year - 1
    if mes in (2, 3, 4):
        return "1T", hoy.year
    if mes in (5, 6, 7):
        return "2T", hoy.year
    return "3T", hoy.year


# --- Contexto que reciben las plantillas --------------------------------
@dataclass
class Contexto:
    periodo: str = "1T"
    anio: int = date.today().year
    cliente: str = ""              # vacio -> se usa la palabra "cliente"
    nif: str = ""
    fecha_limite: date | None = None
    documentos: list[str] = field(default_factory=list)
    # Bloques de documentacion opcional activos: cada uno es (intro, lineas).
    # Se insertan como su propio parrafo + su propia lista, separados de
    # `documentos` (no se mezclan en la misma vineta).
    documentos_extra: list[tuple[str, list[str]]] = field(default_factory=list)
    navidad: bool = False
    notas: str = ""

    @property
    def periodo_largo(self) -> str:
        return PERIODOS[self.periodo]["largo"]

    @property
    def periodo_corto(self) -> str:
        return PERIODOS[self.periodo]["corto"]

    @property
    def fecha_limite_txt(self) -> str:
        d = self.fecha_limite or plazo_por_defecto(self.periodo, self.anio)
        return fecha_larga(d)


@dataclass
class Plantilla:
    id: str
    grupo: str
    nombre: str
    documentos_def: list[str]
    usa_navidad: bool
    titulo_tpl: str
    cuerpo_tpl: str


TEXTO_NAVIDAD_DEF = (
    "Desde Asesoría E. Marín le deseamos una Feliz Navidad y un próspero "
    "año nuevo lleno de alegría, salud y felicidad."
)

DOCS_TRIMESTRE = [
    "Facturas de ingresos y gastos, emitidas y recibidas, correspondientes al trimestre.",
    "Facturas o justificantes pendientes de trimestres anteriores, si quedara alguno por entregar.",
    "Facturas y documentación de compra o venta de bienes de inversión, si ha realizado alguna operación de este tipo.",
]

DOCS_CIERRE = [
    "Facturas de ingresos y gastos, emitidas y recibidas, correspondientes al 4.º trimestre.",
    "Facturas de trimestres anteriores que hayan quedado pendientes, para completar todo el ejercicio.",
    "Facturas y documentación técnica (fotocopia) de compra o venta de bienes de inversión o vehículos comerciales realizada durante el año.",
]

DOCS_RECORD = [
    "Facturas de ingresos (ventas / honorarios) del trimestre.",
    "Facturas de gastos deducibles correspondientes al mismo período.",
    "En caso de arrendamiento: facturas de alquiler y de los gastos asociados.",
    "Cualquier otra documentación contable o justificativa relevante.",
]

DOCS_RENTA = [
    "NIF del arrendatario.",
    "Ingresos percibidos durante el año por el arrendamiento.",
    "Gastos pagados del inmueble (IBI, seguros, comunidad, reparaciones, intereses de préstamo...).",
]


PLANTILLAS: list[Plantilla] = [
    Plantilla(
        id="solicitud_trim",
        grupo="Solicitud de documentación",
        nombre="Solicitud de documentación — Trimestre",
        documentos_def=DOCS_TRIMESTRE,
        usa_navidad=False,
        titulo_tpl="Solicitud de documentación — {periodo} de {anio}",
        cuerpo_tpl="""Estimado/a {cliente}:

Para preparar los impuestos del *{periodo} de {anio}*, necesitamos que nos envíe la siguiente documentación:

{documentos}

{notas}

Por favor, envíenos la documentación *antes del {fecha_limite}* para que podamos revisarla y presentar los impuestos dentro de plazo.

Muchas gracias. Quedamos a su disposición para cualquier consulta.""",
    ),
    Plantilla(
        id="recordatorio",
        grupo="Solicitud de documentación",
        nombre="Recordatorio de plazos — Cierre de trimestre",
        documentos_def=DOCS_RECORD,
        usa_navidad=False,
        titulo_tpl="Recordatorio de plazos — Cierre del {periodo} de {anio}",
        cuerpo_tpl="""Estimado/a {cliente}:

Le recordamos que el plazo de presentación de las liquidaciones correspondientes al *{periodo} de {anio}* es el siguiente:

{tabla_plazos}

Para prepararlas, necesitamos esta documentación:

{documentos}

{notas}

Por favor, envíenosla cuanto antes. Quedamos a su disposición para cualquier consulta.""",
    ),
    Plantilla(
        id="cierre_anual",
        grupo="Cierre de ejercicio",
        nombre="4.º Trimestre + Resumen Anual (cierre de ejercicio)",
        documentos_def=DOCS_CIERRE,
        usa_navidad=True,
        titulo_tpl="Solicitud de documentación — 4.º Trimestre y Resumen Anual {anio}",
        cuerpo_tpl="""Estimado/a {cliente}:

{felicitacion_navidad}

Para preparar el cierre del ejercicio *{anio}*, necesitamos la siguiente documentación:

{documentos}

{notas}

Por favor, envíenosla *antes del {fecha_limite}* para que podamos revisarla y presentar los impuestos dentro de plazo.

Muchas gracias. Quedamos a su disposición para cualquier consulta.""",
    ),
    Plantilla(
        id="renta_arrend",
        grupo="Renta",
        nombre="Renta — Bienes arrendados",
        documentos_def=DOCS_RENTA,
        usa_navidad=False,
        titulo_tpl="Solicitud de información — Bienes arrendados · Renta {anio}",
        cuerpo_tpl="""Estimado/a {cliente}:

Para preparar su declaración de la Renta del ejercicio *{anio}*, necesitamos esta información de cada inmueble que haya tenido arrendado:

{documentos}

{notas}

Por favor, envíenosla *antes del {fecha_limite}* para poder preparar su declaración con tiempo suficiente.

Muchas gracias. Quedamos a su disposición para cualquier consulta.""",
    ),
]


def por_id(pid: str) -> Plantilla:
    for p in PLANTILLAS:
        if p.id == pid:
            return p
    return PLANTILLAS[0]


# ======================================================================
#  Overrides (textos editados por el usuario desde la aplicacion)
# ======================================================================
_overrides_cache: dict[str, dict[str, str]] | None = None


def _overrides_path() -> Path:
    return config.config_dir() / "plantillas_personalizadas.json"


def _overrides_validos(datos: object) -> bool:
    if not isinstance(datos, dict):
        return False
    return all(
        isinstance(plantilla_id, str)
        and isinstance(contenido, dict)
        and isinstance(contenido.get("titulo"), str)
        and isinstance(contenido.get("cuerpo"), str)
        for plantilla_id, contenido in datos.items()
    )


def _overrides() -> dict[str, dict[str, str]]:
    global _overrides_cache
    if _overrides_cache is None:
        datos = config.leer_json(
            _overrides_path(), {}, copias=3, validar=_overrides_validos
        )
        _overrides_cache = datos if isinstance(datos, dict) else {}
    return _overrides_cache


def _guardar_overrides() -> None:
    try:
        config.escribir_json(_overrides_path(), _overrides(), copias=3)
    except Exception:
        pass


def tiene_override(plantilla_id: str) -> bool:
    return plantilla_id in _overrides()


def guardar_override(plantilla_id: str, titulo: str, cuerpo: str) -> None:
    _overrides()[plantilla_id] = {"titulo": titulo, "cuerpo": cuerpo}
    _guardar_overrides()


def restablecer_override(plantilla_id: str) -> None:
    if plantilla_id in _overrides():
        del _overrides()[plantilla_id]
        _guardar_overrides()


def titulo_tpl_activo(plantilla: Plantilla) -> str:
    return _overrides().get(plantilla.id, {}).get("titulo", plantilla.titulo_tpl)


def cuerpo_tpl_activo(plantilla: Plantilla) -> str:
    return _overrides().get(plantilla.id, {}).get("cuerpo", plantilla.cuerpo_tpl)


# ======================================================================
#  Motor de sustitucion de placeholders
# ======================================================================
_RE_NEGRITA = re.compile(r"\*([^*\n]+)\*")
_RE_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _lista_html(items: list[str]) -> str:
    lis = "".join(f"<li>{html.escape(x.strip(), quote=False)}</li>"
                  for x in items if x.strip())
    return f'<ul style="margin:6pt 0;">{lis}</ul>' if lis else ""


def _documentos_html(ctx: Contexto) -> str:
    """Lista base + un parrafo/lista propios por cada bloque de
    documentacion opcional activo (no se mezclan entre si)."""
    bloques = [_lista_html(ctx.documentos)]
    for intro, lineas in ctx.documentos_extra:
        if intro.strip():
            bloques.append(f"<p style='margin:6pt 0;'>{html.escape(intro.strip(), quote=False)}</p>")
        bloques.append(_lista_html(lineas))
    return "".join(b for b in bloques if b)


def _notas_html(notas: str) -> str:
    """Las notas se muestran como un anadido aparte: cursiva, letra mas
    pequena y con el prefijo "Nota:", para distinguirlas del cuerpo
    principal de la carta."""
    lineas = [ln.strip() for ln in notas.strip().splitlines() if ln.strip()]
    if not lineas:
        return ""
    partes = [html.escape(ln, quote=False) for ln in lineas]
    partes[0] = f"Nota: {partes[0]}"
    contenido = "<br/>".join(partes)
    return (f"<p style='margin:6pt 0; font-style:italic; font-size:90%;'>"
            f"{contenido}</p>")


def _tabla_plazos_html(ctx: Contexto) -> str:
    fecha_domiciliacion = html.escape(
        fecha_larga(fecha_domiciliacion_periodo(ctx.periodo, ctx.anio)), quote=False)
    fecha_general = html.escape(
        fecha_larga(fecha_general_periodo(ctx.periodo, ctx.anio)), quote=False)
    borde = "#C9C2AC"
    if ctx.periodo == "4T":
        domiciliacion_tardia = html.escape(
            fecha_larga(fecha_domiciliacion_cierre_tardio(ctx.anio)), quote=False)
        general_tardia = html.escape(
            fecha_larga(fecha_general_cierre_tardio(ctx.anio)), quote=False)
        return f"""<table width="100%" cellpadding="5" cellspacing="0"
       style="border-collapse:collapse; margin:6pt 0;">
  <tr>
    <td style="border:1px solid {borde}; background:#F3F0E6;"><b>Modelos habituales</b></td>
    <td style="border:1px solid {borde}; background:#F3F0E6;"><b>Domiciliación / presentación</b></td>
  </tr>
  <tr>
    <td style="border:1px solid {borde};">Retenciones (111, 115 y similares)</td>
    <td style="border:1px solid {borde};">{fecha_domiciliacion} / {fecha_general}</td>
  </tr>
  <tr>
    <td style="border:1px solid {borde};">Modelos 130, 131, 303 y 309</td>
    <td style="border:1px solid {borde};">{domiciliacion_tardia} / {general_tardia}</td>
  </tr>
</table>"""
    return f"""<table width="100%" cellpadding="5" cellspacing="0"
       style="border-collapse:collapse; margin:6pt 0;">
  <tr>
    <td style="border:1px solid {borde}; background:#F3F0E6;"><b>Modalidad de presentación</b></td>
    <td style="border:1px solid {borde}; background:#F3F0E6;"><b>Plazo límite</b></td>
  </tr>
  <tr>
    <td style="border:1px solid {borde};">Resultado positivo con domiciliación</td>
    <td style="border:1px solid {borde};">Hasta el {fecha_domiciliacion}</td>
  </tr>
  <tr>
    <td style="border:1px solid {borde};">Resto de resultados (negativo, a compensar, aplazamiento)</td>
    <td style="border:1px solid {borde};">Hasta el {fecha_general}</td>
  </tr>
</table>"""


def _cliente_nif(nombre: str, nif_ctx: str) -> str:
    if nif_ctx.strip():
        return nif_ctx.strip()
    try:
        from . import clients
        nombre_norm = nombre.strip().lower()
        if nombre_norm:
            for c in clients.cargar():
                if c.nombre.strip().lower() == nombre_norm:
                    return c.nif
    except Exception:
        pass
    return ""


def _valores_comunes(ctx: Contexto) -> dict[str, str]:
    return {
        "cliente": ctx.cliente.strip() or "cliente",
        "periodo": ctx.periodo_largo,
        "anio": str(ctx.anio),
        "fecha_limite": ctx.fecha_limite_txt,
        "nif": _cliente_nif(ctx.cliente, ctx.nif),
    }


def _valores_titulo(ctx: Contexto) -> dict[str, str]:
    return _valores_comunes(ctx)


def _valores_cuerpo(ctx: Contexto) -> dict[str, str]:
    v = {k: html.escape(val, quote=False) for k, val in _valores_comunes(ctx).items()}
    v["documentos"] = _documentos_html(ctx)
    v["notas"] = _notas_html(ctx.notas)
    v["felicitacion_navidad"] = (
        html.escape(TEXTO_NAVIDAD_DEF, quote=False) if ctx.navidad else "")
    v["tabla_plazos"] = _tabla_plazos_html(ctx)
    return v


def render_titulo_texto(ctx: Contexto, tpl: str) -> str:
    """Sustituye los placeholders de un texto de titulo dado (sin mirar overrides)."""
    valores = _valores_titulo(ctx)
    return _RE_PLACEHOLDER.sub(lambda m: valores.get(m.group(1), m.group(0)), tpl)


def render_titulo(ctx: Contexto, plantilla: Plantilla) -> str:
    return render_titulo_texto(ctx, titulo_tpl_activo(plantilla))


def _procesar_parrafo(texto: str, valores: dict[str, str]) -> str:
    escapado = html.escape(texto, quote=False)
    con_negrita = _RE_NEGRITA.sub(lambda m: f"<b>{m.group(1)}</b>", escapado)
    return _RE_PLACEHOLDER.sub(lambda m: valores.get(m.group(1), m.group(0)), con_negrita)


def render_cuerpo_texto(ctx: Contexto, tpl: str) -> str:
    """Sustituye los placeholders de un texto de cuerpo dado (sin mirar overrides)."""
    valores = _valores_cuerpo(ctx)
    bloques: list[str] = []
    for parrafo in re.split(r"\n\s*\n", tpl.strip()):
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        solo = re.fullmatch(r"\{(\w+)\}", parrafo)
        if solo:
            valor = valores.get(solo.group(1), "")
            if not valor.strip():
                continue
            if valor.lstrip().startswith("<"):
                bloques.append(valor)
            else:
                bloques.append(f'<p>{valor}</p>')
            continue
        texto = _procesar_parrafo(parrafo, valores)
        bloques.append(f'<p>{texto}</p>')
    return "\n".join(bloques)


def render_cuerpo(ctx: Contexto, plantilla: Plantilla) -> str:
    return render_cuerpo_texto(ctx, cuerpo_tpl_activo(plantilla))


PLACEHOLDERS_DISPONIBLES = [
    ("{cliente}", "Nombre del cliente (o «cliente» si se deja en blanco)"),
    ("{periodo}", "Periodo, p. ej. «1.er Trimestre»"),
    ("{anio}", "Año"),
    ("{fecha_limite}", "Fecha límite en texto largo"),
    ("{nif}", "NIF del cliente (si está en la base de datos)"),
    ("{documentos}", "Lista de documentos solicitados (en su propio párrafo)"),
    ("{notas}", "Notas adicionales, si las hay (en su propio párrafo)"),
    ("{tabla_plazos}", "Tabla de plazos — solo en «Recordatorio» (en su propio párrafo)"),
    ("{felicitacion_navidad}", "Felicitación navideña — solo en «Cierre de ejercicio»"),
]
