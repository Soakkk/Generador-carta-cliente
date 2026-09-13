# SDD ledger — plan: docs/superpowers/plans/2026-09-13-suite-oficina-unificada.md

## Preflight

- Rama exigida y activa: `codex/suite-oficina-unificada`.
- Repositorio de trabajo: `/Users/ricardo/Documents/Codex/2026-09-13/ok-x20/work/repos/Generador-carta-cliente`.
- Checkout normal (`GIT_DIR == GIT_COMMON`), limpio al inicio. Se trabaja en el checkout y rama indicados expresamente; no se crea otro worktree.
- Base del trabajo: `61eba7e` (`docs: planificar la suite de oficina`).
- Leídos completos: especificación, plan, TDD, `writing-good-tests.md`, `craft-floor.md`, `executing-plans`, `using-git-worktrees`, `verification-before-completion` y `finishing-a-development-branch`.
- Restricciones: no push, merge ni release; no cambios fuera de este repo; `Facturas-a-Aplifisa` es solo referencia; no trabajo de seguridad; salidas documentales inmutables.

## Decisiones

- Se usa TDD RED→GREEN→REFACTOR para cada comportamiento nuevo y se registra aquí la evidencia.
- La caracterización de Task 1 se ejecuta primero contra el commit base y fija salidas reales; por naturaleza, sus snapshots se incorporan ya verdes sobre el comportamiento existente.
- Impeccable `context` se ejecutó una vez. Informó que no hay `PRODUCT.md`/`DESIGN.md`; el trabajo es una mejora acotada de una UI Qt existente, por lo que el código actual y la especificación aprobada son la autoridad visual.
- El detector de Impeccable es mecánico para HTML/CSS y no aplica a Qt/QSS. En Task 6 se sustituirá por pruebas Qt de tokens, jerarquía, estados, teclado y geometría, más capturas offscreen amplia/portátil e inspección visual en dos rondas como máximo.
- El icono pertenece a una identidad geométrica establecida; se generará de forma determinista para conservar forma, color y resoluciones, no mediante generación raster libre.
- El flujo de publicación se implementará y probará, pero no se ejecutará un release real.
- El host no ofrece `python`; se usa `.venv/bin/python` (Python 3.13.4) con `PySide6 6.11.2` y `pytest 9.1.1` instalados en el entorno ignorado del repo.
- El baseline expuso que el comando literal `python scripts/test_full.py` no incluye la raíz del repo en `sys.path`, y que pytest colecciona scripts ejecutables con efectos de importación. Task 1 corregirá el arnés para que los comandos literales del plan funcionen con el intérprete del entorno.

## Tareas

- [x] Task 1 — Contratos de salida (`a3fc70e`)
- [x] Task 2 — Directorio común y borrador recuperable (`37524d5`)
- [x] Task 3 — Guardar y siguiente cliente (`6a6f51d`)
- [x] Task 4 — Lotes reanudables (`cefd163`)
- [x] Task 5 — Actualización y release automáticos (`3840a09`)
- [x] Task 6 — Interfaz e icono comunes (`aebe13f`)
- [x] Task 7 — Verificación final

## Evidencia TDD y verificación

- Baseline funcional en `61eba7e`: `PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/test_full.py` → `TODO OK` (97 comprobaciones, exit 0).
- Baseline literal: `.venv/bin/python scripts/test_full.py` → FAIL esperado por arnés (`ModuleNotFoundError: avisos`); `.venv/bin/python -m pytest -q` → ERROR de colección por segunda `QApplication` en `scripts/test_preview.py`.
- Task 1 caracterización: comando directo `scripts/test_full.py` → `TODO OK`; `pytest tests/test_regresion_salidas.py -v` → 5 passed; `pytest -q` → 5 passed; `git diff --check` → limpio.
- Task 1 fija hashes exactos de HTML resuelto para cuatro plantillas, edición manual y dos clientes de lote; en macOS fija además hashes SHA-256 exactos del raster A4. En otros sistemas comprueba una página A4 materialmente no vacía para tolerar diferencias del rasterizador de fuentes.
- Task 2 RED: colección falló por ausencia de `avisos.suite_storage` y `avisos.draft`. GREEN: 8/8 pruebas de NIF, fusión, conflicto explícito, importación no destructiva y borrador pasaron. Regresión completa en ese punto: 13 passed y `scripts/test_full.py` → `TODO OK`.
- Task 3 RED: colección falló por ausencia de `clave_orden_cliente` (la nueva superficie pública). GREEN: 8/8 pruebas focales y 17/17 suite pytest. Se verificaron restauración de HTML manual, debounce 300 ms, salida única + historial único, limpieza selectiva, deshacer, recientes/favoritos y búsqueda por NIF.
- Task 4 RED (modelo): colección falló por ausencia de `avisos.batch`. GREEN modelo: 4/4. RED (Qt): `LoteDialog` carecía de `_iniciar_lote`; tras implementar, la primera pasada detectó una expectativa de visibilidad incorrecta en el propio test (se corrigió para exigir la acción visible). GREEN final: 10/10 focales (lote + salidas), 22/22 suite y `scripts/test_full.py` → `TODO OK`.
- Task 5 RED: colección falló por ausencia de estados y `preparar_instalacion`. GREEN: 4/4 pruebas focales; 26/26 suite; `scripts/test_full.py` → `TODO OK`; `compileall` limpio; workflow parseado por Ruby/YAML. La prueba usa `file://` real para descarga+SHA, no simula el resultado. El release real no se ejecutó.
- Task 6 RED heredado tras la interrupción: 2/4 pruebas fallaron porque `MainWindow` aún no exponía `btn_guardar_abrir` ni `_aplicar_modo_compacto`. RED ampliado: 3/5 fallaron al fijar también la jerarquía formulario/documento. GREEN de UI: 5/5. RED de icono: el PNG antiguo carecía de `#326FA6` y `#F2B52D`. GREEN final: 6/6 pruebas focales.
- Task 6 aplica los tokens exactos de la suite, mantiene “Copiar texto” como única acción primaria con `Ctrl+Entrar`, conserva en el menú los accesos ocultos por el modo compacto y acorta las etiquetas que se desbordaban en 1024 px. El editor, vista previa y renderizador documental no se modificaron.
- El icono se reconstruyó de forma determinista desde `assets/app-icon.svg`: rombo `#326FA6`, carta blanca y acento `#F2B52D`; PNG 512×512 e ICO con 16, 24, 32, 48, 64, 128 y 256 px.
- Inspección visual en una ronda conjunta: capturas offscreen 1440×900 y 1024×720 guardadas como `ui-after-wide.png` y `ui-after-portable.png`; no se observaron recortes ni defectos que exigieran una segunda ronda.
- Detector Impeccable ejecutado una sola vez sobre `avisos/tema_ui.py avisos/app.py avisos/ui` → `[]`.
- Verificación final en `aebe13f`: `.venv/bin/python scripts/test_full.py` → `TODO OK` (97 comprobaciones); `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` → 32 passed; `.venv/bin/python -m compileall -q avisos` → exit 0; `git diff --check` → exit 0.
- La ejecución offscreen en macOS emite avisos informativos del backend Qt sobre alias de fuente y `raise()`; no hay fallos ni warnings de pytest. No se construyó ni publicó un instalador Windows y no se ejecutó un release, conforme a la restricción expresa.

## Única ronda de corrección posterior a revisión final

- [x] Contrato común `schema_version/clientes`: lectura del contrato canónico, migración sin pérdida del formato experimental y conservación de extensiones/clientes ajenos (`ce0a47f`).
- [x] Aislamiento de `APPDATA` y `LOCALAPPDATA` antes de importar la aplicación en `scripts/test_full.py` (`46c5567`).
- [x] Reanudación de lotes con restauración validada de periodo, ejercicio, documentos, bloques opcionales, fecha, Navidad, notas, etiquetas y texto exacto (`c239d2f`).
- [x] Fases persistentes de PDF e historial: un fallo posterior conserva la ruta y el reintento no duplica PDF ni registro confirmado (`3923517`).
- [x] SHA-256 asociado por nombre al EXE concreto de la release (`63095e4`).
- [x] Instalador preparado conservado/reutilizado, estado `ready` bloqueante y temporales exclusivos por descarga (`4649148`).
- [x] Conflictos del directorio común mostrados y resueltos explícitamente desde la edición de clientes (`9bdb5cc`).
- [x] Tres copias rotativas y recuperación JSON validada por tipo para historial y plantillas personalizadas (`2244e2b`).
- [x] Deshacer limitado de la última eliminación de documento, conservando posición y texto (`e429e14`).

Evidencia TDD: cada reproducción nueva falló antes de su corrección y pasó después; las pruebas focales quedaron incorporadas sin reducir las existentes. Verificación posterior en `e429e14`: `scripts/test_full.py` → `TODO OK` (97 comprobaciones); pytest offscreen → 45 passed; `compileall` → exit 0; `git diff --check` del rango → exit 0; contratos de salida → 5 passed. No se modificaron `render.py`, `estilo.py`, `extras.py`, el logo documental, el cuerpo ZIP ni el workflow de release. No se ejecutó detector Impeccable de nuevo porque el ledger ya registraba su única ejecución.
