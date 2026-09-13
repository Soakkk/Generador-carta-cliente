from __future__ import annotations

import json

import pytest

from avisos import clients
from avisos.suite_storage import (
    fusionar_cliente,
    listar_clientes_comunes,
    normalizar_nif,
)


@pytest.fixture
def datos_aislados(monkeypatch, tmp_path):
    appdata = tmp_path / "appdata"
    localappdata = tmp_path / "localappdata"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))
    return appdata, localappdata


def test_normalizar_nif_unifica_separadores_y_mayusculas():
    """Dejar espacios o guiones impediría fusionar el mismo contribuyente."""
    assert normalizar_nif(" b-12 345.678 ") == "B12345678"


def test_fusion_rellena_campos_vacios_y_conserva_metadatos(tmp_path):
    """Omitir procedencia/fecha haría imposible resolver conflictos futuros."""
    resultado = fusionar_cliente(
        {
            "nombre": "Acme SL",
            "nif": "b-12345678",
            "direccion": "Calle Mayor 1",
            "iban": "ES12 3456",
            "telefono": "600 000 000",
            "email": "hola@acme.es",
        },
        origen="AvisosEMarin",
        actualizado="2026-09-13T10:00:00+00:00",
        root=tmp_path,
    )

    assert resultado.conflictos == []
    assert resultado.cliente["nif"] == "B12345678"
    assert resultado.cliente["direccion"] == "Calle Mayor 1"
    registro = json.loads((tmp_path / "clientes.json").read_text("utf-8"))
    assert registro["schema"] == 1
    assert registro["clientes"]["B12345678"]["campos"]["email"] == {
        "valor": "hola@acme.es",
        "origen": "AvisosEMarin",
        "actualizado": "2026-09-13T10:00:00+00:00",
    }
    assert not (tmp_path / "clientes.json.tmp").exists()


def test_conflicto_no_pisa_valor_y_se_puede_resolver_expresamente(tmp_path):
    """Sobrescribir un valor distinto sin decisión perdería datos recientes."""
    fusionar_cliente(
        {"nif": "12345678A", "nombre": "Ana", "email": "antes@example.com"},
        origen="FacturasAplifisa",
        actualizado="2026-09-13T09:00:00+00:00",
        root=tmp_path,
    )

    pendiente = fusionar_cliente(
        {"nif": "12345678-A", "nombre": "Ana", "email": "nuevo@example.com"},
        origen="AvisosEMarin",
        actualizado="2026-09-13T10:00:00+00:00",
        root=tmp_path,
    )
    assert [c.campo for c in pendiente.conflictos] == ["email"]
    assert pendiente.cliente["email"] == "antes@example.com"

    resuelto = fusionar_cliente(
        {"nif": "12345678A", "nombre": "Ana", "email": "nuevo@example.com"},
        origen="AvisosEMarin",
        actualizado="2026-09-13T10:00:00+00:00",
        resolver={"email": "entrante"},
        root=tmp_path,
    )
    assert resuelto.conflictos == []
    assert resuelto.cliente["email"] == "nuevo@example.com"


def test_clientes_importa_sin_borrar_la_base_anterior(datos_aislados):
    """Migrar al directorio común no debe eliminar el JSON histórico local."""
    appdata, localappdata = datos_aislados
    legacy = appdata / "AvisosEMarin" / "clientes.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps([
            {"nombre": "Cliente antiguo", "nif": "11111111H", "telefono": "600"}
        ]),
        "utf-8",
    )
    fusionar_cliente(
        {"nombre": "Cliente compartido", "nif": "22222222J", "email": "c@example.com"},
        origen="FacturasAplifisa",
        root=localappdata / "AsesoriaEMarin" / "Suite",
    )

    cargados = clients.cargar()
    assert [c.nombre for c in cargados] == ["Cliente antiguo", "Cliente compartido"]
    assert json.loads(legacy.read_text("utf-8"))[0]["nombre"] == "Cliente antiguo"

    clients.guardar(cargados)
    assert legacy.exists()
    comunes = listar_clientes_comunes()
    assert {c["nif"] for c in comunes} == {"11111111H", "22222222J"}

