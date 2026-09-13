from __future__ import annotations

from avisos.draft import borrar_borrador, guardar_borrador, leer_borrador


def test_borrador_conserva_html_editado(tmp_path):
    """Perder el HTML manual al reiniciar destruiría una edición pendiente."""
    guardar_borrador({"editor_html": "<p><b>Texto propio</b></p>"}, root=tmp_path)
    assert leer_borrador(root=tmp_path)["editor_html"] == "<p><b>Texto propio</b></p>"
    assert not (tmp_path / "borrador-avisos.json.tmp").exists()


def test_borrador_round_trip_conserva_toda_la_sesion(tmp_path):
    """Eliminar listas o selecciones impediría reanudar el aviso exactamente."""
    esperado = {
        "plantilla_id": "recordatorio",
        "cliente": "Acme SL",
        "nif": "B12345678",
        "periodo": "2T",
        "anio": 2026,
        "documentos": ["Factura A", "Factura B"],
        "extras": ["Inmueble"],
        "editor_html": "<p>Edición manual</p>",
        "editor_dirty": True,
    }
    guardar_borrador(esperado, root=tmp_path)
    assert leer_borrador(root=tmp_path) == esperado


def test_borrar_borrador_es_idempotente(tmp_path):
    """Una limpieza repetida no debe fallar ni revivir datos antiguos."""
    guardar_borrador({"cliente": "Ana"}, root=tmp_path)
    borrar_borrador(root=tmp_path)
    borrar_borrador(root=tmp_path)
    assert leer_borrador(root=tmp_path) is None


def test_borrador_corrupto_no_impide_arrancar(tmp_path):
    """Un corte durante una versión antigua no debe bloquear la aplicación."""
    (tmp_path / "borrador-avisos.json").write_text("{corrupto", "utf-8")
    assert leer_borrador(root=tmp_path) is None

