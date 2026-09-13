from __future__ import annotations

from pathlib import Path

from avisos.batch import BatchItem, BatchState, cargar_lote, guardar_lote


def test_dialogo_muestra_cola_progreso_y_acciones_de_resumen(monkeypatch, tmp_path):
    """Ocultar estados impediría saber qué cliente falló o ya terminó."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    from PySide6.QtWidgets import QApplication
    from avisos.templates import Contexto, PLANTILLAS
    from avisos.ui.lote import LoteDialog

    app = QApplication.instance() or QApplication([])
    destino = tmp_path / "pdf"
    destino.mkdir()
    dialogo = LoteDialog(None, Contexto(), PLANTILLAS[0], str(destino))
    dialogo._iniciar_lote(["Uno SL", "Dos SL"])
    dialogo._lote.marcar_ok("1", str(destino / "uno.pdf"))
    dialogo._lote.siguiente()
    dialogo._lote.marcar_error("2", "No se pudo escribir")
    dialogo._actualizar_cola()

    assert dialogo.tabla_cola.rowCount() == 2
    assert dialogo.tabla_cola.item(0, 1).text() == "Completado"
    assert dialogo.tabla_cola.item(1, 1).text() == "Fallido"
    assert dialogo.progreso.maximum() == 2
    assert dialogo.progreso.value() == 2
    assert dialogo.btn_reintentar.isVisibleTo(dialogo) is True
    assert dialogo.btn_reintentar.text() == "Reintentar fallidos"
    assert dialogo.btn_abrir_carpeta.text() == "Abrir carpeta"
    assert dialogo.btn_terminar.text() == "Terminar"
    dialogo.deleteLater()
    app.processEvents()


def _estado() -> BatchState:
    return BatchState(items=[
        BatchItem(id="1", cliente_nif="11111111H", nombre="Uno SL"),
        BatchItem(id="2", cliente_nif="22222222J", nombre="Dos SL"),
        BatchItem(id="3", cliente_nif="33333333P", nombre="Tres SL"),
    ])


def test_un_error_no_repite_clientes_completados():
    """Elegir de nuevo un completado duplicaría su PDF y su historial."""
    lote = _estado()
    primero = lote.siguiente()
    assert primero.id == "1"
    lote.marcar_ok("1", "/tmp/uno.pdf")
    segundo = lote.siguiente()
    assert segundo.id == "2"
    lote.marcar_error("2", "Disco lleno")

    assert lote.siguiente().id == "3"
    lote.marcar_ok("3", "/tmp/tres.pdf")
    assert lote.siguiente() is None
    assert lote.por_id("1").intentos == 1

    lote.reintentar_fallidos()
    assert lote.siguiente().id == "2"
    assert lote.por_id("1").estado == "completado"
    assert lote.por_id("1").intentos == 1


def test_cancelar_conserva_estado_y_reanuda_solo_pendientes(tmp_path):
    """Cancelar no debe perder la cola ni convertir pendientes en completados."""
    lote = _estado()
    lote.marcar_ok("1", "/tmp/uno.pdf")
    lote.cancelar()
    guardar_lote(lote, root=tmp_path)

    restaurado = cargar_lote(root=tmp_path)
    assert restaurado.cancelado is True
    assert restaurado.por_id("1").estado == "completado"
    assert restaurado.por_id("2").estado == "pendiente"
    assert restaurado.siguiente() is None

    restaurado.reanudar()
    assert restaurado.siguiente().id == "2"


def test_interrupcion_devuelve_generando_a_pendiente():
    """Un cierre durante render no debe dejar un elemento bloqueado para siempre."""
    lote = _estado()
    assert lote.siguiente().estado == "generando"
    restaurado = BatchState.from_dict(lote.to_dict())
    assert restaurado.por_id("1").estado == "pendiente"
    assert restaurado.siguiente().id == "1"


def test_estado_serializa_configuracion_de_serie_y_escribe_atomicamente(tmp_path):
    """Perder destino/modo/configuración impediría reanudar la misma serie."""
    lote = _estado()
    lote.carpeta = "C:/Avisos"
    lote.modo_salida = "pdf"
    lote.configuracion = {"plantilla_id": "recordatorio", "periodo": "2T"}
    guardar_lote(lote, root=tmp_path)

    restaurado = cargar_lote(root=tmp_path)
    assert restaurado.carpeta == "C:/Avisos"
    assert restaurado.modo_salida == "pdf"
    assert restaurado.configuracion == {"plantilla_id": "recordatorio", "periodo": "2T"}
    assert not (tmp_path / "lote-avisos.json.tmp").exists()


def test_dialogo_reanuda_con_todo_el_contexto_persistido(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    from PySide6.QtWidgets import QApplication
    from avisos.templates import Contexto, PLANTILLAS
    from avisos.ui.lote import LoteDialog

    app = QApplication.instance() or QApplication([])
    destino = tmp_path / "pdf"
    destino.mkdir()
    guardado = BatchState(
        items=[BatchItem(id="1", cliente_nif="", nombre="Uno")],
        carpeta=str(destino),
        configuracion={
            "plantilla_id": PLANTILLAS[0].id,
            "periodo": "1T",
            "anio": 2025,
            "documentos": ["Documento anterior"],
            "documentos_extra": [["Bloque", ["Extra anterior"]]],
            "fecha_limite": "2025-04-15",
            "navidad": True,
            "notas": "Nota anterior",
            "extras": ["Etiqueta anterior"],
            "titulo_tpl": "Título anterior {anio}",
            "cuerpo_tpl": "Cuerpo anterior {documentos}",
        },
    )
    guardar_lote(guardado)

    dialogo = LoteDialog(
        None,
        Contexto(periodo="2T", anio=2026, documentos=["Documento nuevo"]),
        PLANTILLAS[0],
        str(destino),
        documento_tpl=("Título nuevo", "Cuerpo nuevo"),
        extras_etiquetas=["Etiqueta nueva"],
    )

    assert dialogo._ctx_base.periodo == "1T"
    assert dialogo._ctx_base.anio == 2025
    assert dialogo._ctx_base.documentos == ["Documento anterior"]
    assert dialogo._ctx_base.notas == "Nota anterior"
    assert dialogo._documento_tpl == ("Título anterior {anio}", "Cuerpo anterior {documentos}")
    assert dialogo._extras_etiquetas == ["Etiqueta anterior"]
    dialogo.deleteLater()
    app.processEvents()


def test_lote_ya_completado_no_restaura_contexto_en_serie_nueva(monkeypatch, tmp_path):
    """Reabrir tras terminar no debe contaminar una serie nueva con datos antiguos."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    from PySide6.QtWidgets import QApplication
    from avisos.templates import Contexto, PLANTILLAS
    from avisos.ui.lote import LoteDialog

    app = QApplication.instance() or QApplication([])
    destino = tmp_path / "pdf"
    destino.mkdir()
    guardado = BatchState(
        items=[BatchItem(
            id="1", cliente_nif="", nombre="Terminado", estado="completado",
            salida=str(destino / "terminado.pdf"), pdf_generado=True,
            historial_registrado=True,
        )],
        carpeta=str(destino),
        configuracion={
            "plantilla_id": PLANTILLAS[0].id,
            "periodo": "1T",
            "anio": 2025,
            "documentos": ["Documento anterior"],
            "extras": ["Etiqueta anterior"],
            "titulo_tpl": "Título anterior",
            "cuerpo_tpl": "Cuerpo anterior",
        },
    )
    guardar_lote(guardado)

    actual = Contexto(periodo="2T", anio=2026, documentos=["Documento nuevo"])
    dialogo = LoteDialog(
        None, actual, PLANTILLAS[0], str(destino),
        documento_tpl=("Título nuevo", "Cuerpo nuevo"),
        extras_etiquetas=["Etiqueta nueva"],
    )

    assert dialogo._lote is None
    assert dialogo._ctx_base.periodo == "2T"
    assert dialogo._ctx_base.anio == 2026
    assert dialogo._ctx_base.documentos == ["Documento nuevo"]
    assert dialogo._documento_tpl == ("Título nuevo", "Cuerpo nuevo")
    assert dialogo._extras_etiquetas == ["Etiqueta nueva"]
    dialogo.deleteLater()
    app.processEvents()


def test_reintento_tras_fallo_de_registro_no_duplica_el_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    from PySide6.QtWidgets import QApplication
    from avisos.templates import Contexto, PLANTILLAS
    from avisos.ui import lote as modulo_lote

    app = QApplication.instance() or QApplication([])
    destino = tmp_path / "pdf"
    destino.mkdir()
    dialogo = modulo_lote.LoteDialog(None, Contexto(), PLANTILLAS[0], str(destino))
    dialogo._iniciar_lote(["Uno SL"])
    renders: list[str] = []
    registros = 0

    def render_falso(_ctx, _titulo, _cuerpo, ruta):
        renders.append(str(ruta))
        ruta.write_bytes(b"pdf")

    def registrar_falso(*_args, **_kwargs):
        nonlocal registros
        registros += 1
        if registros == 1:
            raise RuntimeError("historial bloqueado")

    monkeypatch.setattr(modulo_lote, "render_pdf_plantilla_texto", render_falso)
    monkeypatch.setattr(modulo_lote.H, "registrar", registrar_falso)
    monkeypatch.setattr(modulo_lote.C, "cargar", lambda: [])
    monkeypatch.setattr(modulo_lote.C, "asegurar_cliente", lambda *_a: None)
    monkeypatch.setattr(modulo_lote.C, "registrar_uso", lambda *_a: None)

    dialogo._procesar_lote()
    item = dialogo._lote.por_id("1")
    assert item.estado == "fallido"
    assert item.salida == renders[0]
    assert Path(item.salida).exists()

    dialogo._reintentar_fallidos()
    assert dialogo._lote.por_id("1").estado == "completado"
    assert renders == [item.salida]
    assert list(destino.glob("*.pdf")) == [Path(item.salida)]
    dialogo.deleteLater()
    app.processEvents()
