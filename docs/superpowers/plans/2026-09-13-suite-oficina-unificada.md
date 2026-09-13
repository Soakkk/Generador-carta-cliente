# Generador de cartas — Suite de oficina Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar la interfaz y acelerar borradores, clientes y lotes manteniendo exactamente los textos y PDF actuales.

**Architecture:** Servicios puros nuevos gestionan directorio común, borrador y cola de lote; los diálogos Qt consumen esas interfaces. `templates.py` y `render.py` quedan protegidos por caracterización.

**Tech Stack:** Python 3.11+, PySide6, JSON local, pytest/script tests, PyInstaller, Inno Setup, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-suite-oficina-unificada-design.md`

## Global Constraints

- No cambiar plantillas, HTML resuelto, logo, formato ni bytes visuales de PDF salvo metadatos no visuales inevitables.
- Windows 10/11; datos bajo `%LOCALAPPDATA%`/`%APPDATA%`.
- Tokens visuales exactos de la especificación, solo en la interfaz de trabajo.
- Las ediciones manuales nunca se regeneran silenciosamente.

---

### Task 1: Contratos de salida

**Files:**
- Modify: `scripts/test_full.py`
- Create: `tests/test_regresion_salidas.py`

**Interfaces:**
- Consumes: `templates`, `render_pdf_plantilla_texto` y casos actuales de `scripts/test_full.py`.
- Produces: snapshots normalizados de texto y raster/hashes de PDF.

- [ ] **Step 1: Extraer casos fijos para cada plantilla, edición manual y lote**
- [ ] **Step 2: Ejecutar `python scripts/test_full.py`; Expected: PASS sobre el commit base**
- [ ] **Step 3: Añadir comparación del texto resuelto y raster de páginas, ignorando metadatos de fecha del PDF**
- [ ] **Step 4: Ejecutar `python -m pytest tests/test_regresion_salidas.py -v`; Expected: PASS**
- [ ] **Step 5: Commit**

```bash
git add scripts/test_full.py tests/test_regresion_salidas.py
git commit -m "test: fijar las salidas de cartas y avisos"
```

### Task 2: Directorio común y borrador recuperable

**Files:**
- Create: `avisos/suite_storage.py`
- Create: `avisos/draft.py`
- Create: `tests/test_suite_storage.py`
- Create: `tests/test_draft.py`
- Modify: `avisos/clients.py`

**Interfaces:**
- Produces: `normalizar_nif`, `listar_clientes_comunes`, `fusionar_cliente`, `guardar_borrador`, `leer_borrador`, `borrar_borrador`.

- [ ] **Step 1: Probar importación no destructiva, conflicto por campo y round-trip de edición manual**

```python
def test_borrador_conserva_html_editado(tmp_path):
    guardar_borrador({"editor_html": "<p><b>Texto propio</b></p>"}, root=tmp_path)
    assert leer_borrador(root=tmp_path)["editor_html"] == "<p><b>Texto propio</b></p>"
```

- [ ] **Step 2: Ejecutar `python -m pytest tests/test_suite_storage.py tests/test_draft.py -v`; Expected: FAIL**
- [ ] **Step 3: Implementar esquema 1, procedencia/fecha por campo, fusión y escritura atómica**

```python
registro = {"schema": 1, "clientes": {}}
registro["clientes"][nif] = {
    "campos": {clave: {"valor": valor, "origen": origen, "actualizado": ahora}}
}
```
- [ ] **Step 4: Adaptar `clients.py` para leer ambas fuentes y escribir sin eliminar su JSON actual**
- [ ] **Step 5: Ejecutar las pruebas; Expected: PASS**
- [ ] **Step 6: Commit**

```bash
git add avisos/suite_storage.py avisos/draft.py avisos/clients.py tests/test_suite_storage.py tests/test_draft.py
git commit -m "feat: compartir clientes y recuperar borradores"
```

### Task 3: Guardar y siguiente cliente

**Files:**
- Modify: `avisos/app.py`
- Modify: `avisos/history.py`
- Modify: `avisos/ui/clientes.py`
- Create: `tests/test_flujo_siguiente.py`

**Interfaces:**
- Produces: `MainWindow._guardar_y_siguiente(abrir: bool)`, `_serializar_borrador()`, `_restaurar_borrador(datos)`, `clientes_recientes(limite=8)` y favoritos persistentes.

- [ ] **Step 1: Probar que conserva plantilla/periodo/docs y limpia nombre/NIF sin tocar una edición pendiente**
- [ ] **Step 2: Ejecutar prueba; Expected: FAIL por método inexistente**
- [ ] **Step 3: Conectar autosave con debounce de 300 ms y restauración al arrancar**

```python
self._timer_borrador = QTimer(self, singleShot=True, interval=300)
self._timer_borrador.timeout.connect(
    lambda: guardar_borrador(self._serializar_borrador()))
```
- [ ] **Step 4: Implementar acción final con un registro único en historial y opción de deshacer cambio de cliente**
- [ ] **Step 5: Añadir recientes/favoritos al buscador existente, ordenados por favorito y última utilización**

```python
def clave_orden_cliente(cliente):
    return (not cliente.get("favorito", False), -cliente.get("ultimo_uso", 0), cliente["nombre"].casefold())
```
- [ ] **Step 6: Ejecutar `python -m pytest tests/test_flujo_siguiente.py tests/test_draft.py -v`; Expected: PASS**
- [ ] **Step 7: Commit**

```bash
git add avisos/app.py avisos/history.py avisos/ui/clientes.py tests/test_flujo_siguiente.py
git commit -m "feat: recuperar avisos y continuar con el siguiente cliente"
```

### Task 4: Lotes reanudables

**Files:**
- Create: `avisos/batch.py`
- Modify: `avisos/ui/lote.py`
- Create: `tests/test_batch.py`

**Interfaces:**
- Produces: `BatchItem(id, cliente_nif, estado, salida, error, intentos)`, `BatchState.siguiente()`, `marcar_ok`, `marcar_error`, `reintentar_fallidos`.

- [ ] **Step 1: Probar que un error no repite clientes completados y que cancelar conserva el estado**
- [ ] **Step 2: Ejecutar `python -m pytest tests/test_batch.py -v`; Expected: FAIL**
- [ ] **Step 3: Implementar modelo puro serializable y adaptarlo al diálogo con progreso por elemento**

```python
@dataclass
class BatchItem:
    id: str
    cliente_nif: str
    estado: str = "pendiente"
    salida: str = ""
    error: str = ""
    intentos: int = 0
```
- [ ] **Step 4: Añadir resumen con Abrir carpeta, Reintentar fallidos y Terminar**
- [ ] **Step 5: Ejecutar `python -m pytest tests/test_batch.py tests/test_regresion_salidas.py -v`; Expected: PASS**
- [ ] **Step 6: Commit**

```bash
git add avisos/batch.py avisos/ui/lote.py tests/test_batch.py
git commit -m "feat: hacer reanudables los lotes de cartas"
```

### Task 5: Actualización y release automáticos

**Files:**
- Modify: `avisos/updater.py`
- Modify: `avisos/ui/actualizaciones.py`
- Modify: `avisos/app.py`
- Modify: `scripts/release.py`
- Modify: `.github/workflows/build.yml`
- Create: `tests/test_updater.py`

**Interfaces:**
- Produces: estados comunes de actualización y `preparar_instalacion(act) -> Path`.

- [ ] **Step 1: Probar descarga automática, SHA, sesión guardada y reintento periódico**
- [ ] **Step 2: Ejecutar `python -m pytest tests/test_updater.py -v`; Expected: FAIL**
- [ ] **Step 3: Implementar descarga en hilo y estado ready; instalar en cierre limpio o por botón**

```python
def _actualizacion_lista(self, ruta: str) -> None:
    self._ruta_update_lista = ruta
    self.lbl_estado.setText("Actualización lista · se instalará al cerrar")
```
- [ ] **Step 4: Convertir release en un comando/workflow que prueba, construye, genera hash y publica**
- [ ] **Step 5: Ejecutar batería completa; Expected: PASS**
- [ ] **Step 6: Commit**

```bash
git add avisos/updater.py avisos/ui/actualizaciones.py avisos/app.py scripts/release.py .github/workflows/build.yml tests/test_updater.py
git commit -m "feat: automatizar actualizaciones y publicaciones"
```

### Task 6: Interfaz e icono comunes

**Files:**
- Modify: `avisos/tema_ui.py`
- Modify: `avisos/app.py`
- Modify: `avisos/ui/*.py`
- Modify: `assets/app-icon.png`
- Modify: `assets/app.ico`
- Create: `tests/test_tema_ui.py`

**Interfaces:**
- Produces: shell claro adaptable y estados comunes; no altera el widget de vista previa.

- [ ] **Step 1: Probar tokens exactos, acciones principales y modo compacto**
- [ ] **Step 2: Ejecutar prueba; Expected: FAIL sobre la paleta anterior**
- [ ] **Step 3: Aplicar QSS y reorganizar barras/acciones fuera del renderizador**

```python
PAGE = "#F5F8FC"; CARD = "#FFFFFF"; INK = "#24384D"
MUTED = "#5D7084"; BORDER = "#DCE5F0"; ACCENT = "#326FA6"
SUCCESS = "#19724E"; WARNING = "#86500A"; DANGER = "#B43737"
```
- [ ] **Step 4: Generar icono rombo azul con carta blanca y acento dorado, PNG 512 e ICO multirresolución**
- [ ] **Step 5: Inspeccionar una captura amplia y otra portátil, arreglar en un lote y confirmar una vez**
- [ ] **Step 6: Ejecutar `python scripts/test_full.py && python -m pytest -q`; Expected: PASS y salidas idénticas**
- [ ] **Step 7: Commit**

```bash
git add avisos/tema_ui.py avisos/app.py avisos/ui assets/app-icon.png assets/app.ico tests/test_tema_ui.py
git commit -m "feat: integrar cartas en la identidad de la suite"
```

### Task 7: Verificación final

- [ ] **Step 1: Ejecutar `python scripts/test_full.py`**
- [ ] **Step 2: Ejecutar `python -m pytest -q`**
- [ ] **Step 3: Ejecutar `python -m compileall -q avisos`**
- [ ] **Step 4: Ejecutar detector visual una vez sobre `avisos/tema_ui.py avisos/app.py avisos/ui`**
- [ ] **Step 5: Revisar `git diff --check` y el conjunto final de commits**
