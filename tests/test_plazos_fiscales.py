from datetime import date

from avisos import templates


def test_tercer_trimestre_2026_coincide_con_calendario_aeat():
    assert templates.periodo_sugerido_hoy(date(2026, 9, 22)) == ("3T", 2026)
    assert templates.fecha_domiciliacion_periodo("3T", 2026) == date(2026, 10, 15)
    assert templates.fecha_general_periodo("3T", 2026) == date(2026, 10, 20)


def test_cuarto_trimestre_separa_retenciones_de_iva_y_pagos_fraccionados():
    assert templates.fecha_domiciliacion_periodo("4T", 2025) == date(2026, 1, 15)
    assert templates.fecha_general_periodo("4T", 2025) == date(2026, 1, 20)
    assert templates.fecha_domiciliacion_cierre_tardio(2025) == date(2026, 1, 27)
    assert templates.fecha_general_cierre_tardio(2025) == date(2026, 1, 30)


def test_tabla_de_plazos_no_confunde_fecha_interna_con_vencimiento_fiscal():
    ctx = templates.Contexto(
        periodo="3T", anio=2026, fecha_limite=date(2026, 9, 30))
    tabla = templates._tabla_plazos_html(ctx)
    assert "15 de octubre de 2026" in tabla
    assert "20 de octubre de 2026" in tabla
    assert "30 de septiembre de 2026" not in tabla
