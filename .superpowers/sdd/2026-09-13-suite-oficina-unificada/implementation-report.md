# Implementation report — suite de oficina unificada

Fecha: 13 de septiembre de 2026
Rama: `codex/suite-oficina-unificada`
Base: `e1f9f87` (`v1.10.0`)

## Estado

Las siete tareas del plan `docs/superpowers/plans/2026-09-13-suite-oficina-unificada.md`, la ronda de corrección de los nueve hallazgos finales y los dos hallazgos Important de la re-revisión están implementados y verificados. La rama queda conservada sin merge, push, PR, release ni publicación.

Se mantuvieron intactos los contratos de plantillas, HTML resuelto, carta, logo documental, paginación y raster/PDF. Los únicos recursos gráficos sustituidos son el icono de la aplicación pedido por la Task 6 (`assets/app-icon.png` y `assets/app.ico`), con `assets/app-icon.svg` como fuente reproducible.

## Commits de implementación

- `a3fc70e` — `test: fijar las salidas de cartas y avisos`
- `37524d5` — `feat: compartir clientes y recuperar borradores`
- `6a6f51d` — `feat: recuperar avisos y continuar con el siguiente cliente`
- `cefd163` — `feat: hacer reanudables los lotes de cartas`
- `3840a09` — `feat: automatizar actualizaciones y publicaciones`
- `aebe13f` — `feat: integrar cartas en la identidad de la suite`
- `ce0a47f` — `fix: migrar sin perdida el directorio comun`
- `46c5567` — `test: aislar el directorio comun en la bateria funcional`
- `c239d2f` — `fix: restaurar el contexto exacto al reanudar lotes`
- `3923517` — `fix: separar generacion y registro de lotes`
- `63095e4` — `fix: asociar checksum al instalador exacto`
- `4649148` — `fix: conservar actualizaciones ya preparadas`
- `9bdb5cc` — `fix: mostrar y resolver conflictos de clientes`
- `2244e2b` — `fix: recuperar historial y plantillas desde copias`
- `e429e14` — `fix: permitir deshacer documentos eliminados`
- `0a2ab7c` — `fix: ignorar lotes ya completados al crear series`
- `731460d` — `fix: validar backups antes de recuperar datos`

## Resultado funcional

- Directorio común de clientes con fusión por NIF, procedencia/fecha por campo y conflictos explícitos.
- Borrador completo recuperable, autosave con debounce, recientes/favoritos y deshacer de cliente.
- “Guardar y siguiente cliente” con un único PDF y registro de historial por operación.
- Lotes reanudables con estados por cliente, cancelación segura y reintento solo de fallidos.
- Descarga y validación SHA de actualizaciones, sesión preservada e instalación diferible.
- Flujo automatizado de build/hash/publicación configurado, sin ejecutar un release real.
- Interfaz Qt con los tokens exactos de la suite, estados de foco/disabled/error, acción primaria única, `Ctrl+Entrar`, paneles jerarquizados y modo compacto para 1024 px.
- Icono común: rombo azul, carta blanca y acento dorado; PNG 512 e ICO multirresolución.
- Directorio común compatible con el contrato canónico y migración del formato experimental sin pérdida.
- Lotes reanudados con su contexto completo y fases persistentes que evitan duplicar PDF/historial.
- Actualizador ligado al hash del EXE, con instalador listo preservado y descargas temporales exclusivas.
- Conflictos de clientes resolubles en pantalla, recuperación desde copias rotativas y deshacer de documentos.
- Los lotes completados no contaminan series nuevas; solo una cola pendiente o fallida restaura su contexto.
- Historial y plantillas eligen una copia únicamente después de validar la estructura y tipos internos.

## Evidencia

- `.venv/bin/python scripts/test_full.py` → `TODO OK` (97 comprobaciones).
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` → `48 passed in 1.38s`.
- `.venv/bin/python -m compileall -q avisos` → exit 0.
- `git diff --check` → exit 0.
- Detector visual Impeccable sobre `avisos/tema_ui.py avisos/app.py avisos/ui` → `[]`.
- Capturas verificadas: `ui-after-wide.png` (1440×900) y `ui-after-portable.png` (1024×720), sin recortes observados.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_regresion_salidas.py` → `5 passed`; sin cambios en `render.py`, `estilo.py`, `extras.py`, logo documental, ZIP ni workflow de release.

## Consideraciones pendientes de integración

- Qt offscreen en macOS imprime avisos informativos sobre alias de fuente y la operación `raise()`; las pruebas terminan en verde y pytest no informa warnings.
- El instalador Windows y el release real no se ejecutaron en este host: deben pasar por el workflow configurado antes de publicar. Esta omisión es deliberada por la instrucción de no hacer release/publicación.
- El detector mecánico está orientado principalmente a HTML/CSS; la cobertura efectiva de Qt/QSS procede de seis pruebas focales y de las capturas en los dos tamaños objetivo.
