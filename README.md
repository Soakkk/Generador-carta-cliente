# Avisos Asesoría E. Marín

Herramienta de escritorio para generar los **avisos a clientes** (solicitud de
documentación, recordatorios de plazos, cierre de ejercicio, Renta…) siempre con
la **misma estética** de la asesoría y exportarlos a **PDF** para guardar y enviar.

El objetivo es tener un único estilo, coherente con el manual de marca (logo,
colores y pie de página fijos), y poder cambiar solo los datos de cada aviso:
periodo, año, fecha límite, nombre del cliente y la lista de documentos.

![logo](assets/EM_logo_horizontal_claro.jpg)

## Características

- Plantillas predefinidas con la redacción real de la oficina:
  - **Solicitud de documentación — Trimestre**
  - **Recordatorio de plazos — Cierre de trimestre**
  - **4.º Trimestre + Resumen Anual (cierre de ejercicio)** (con felicitación navideña opcional)
  - **Renta — Bienes arrendados**
- **Panel de trabajo directo**: sin asistente por pasos. La plantilla, cliente,
  periodo, fecha y documentación quedan a la izquierda; la vista previa real del
  PDF permanece visible a la derecha y las acciones de guardado están siempre
  disponibles en una barra inferior fija.
- Selectores rediseñados, nombres de plantilla más legibles y periodos mediante
  botones directos (`1T`, `2T`, `3T`, `4T`, `Renta`). La rueda del ratón desplaza
  la pantalla, pero **no cambia accidentalmente** plantillas, años, fechas, fuentes
  ni valores numéricos.
- Periodo y **año se sugieren solos** según la fecha del sistema. La aplicación muestra
  juntas las fechas orientativas de **domiciliación** y **presentación** de los modelos
  trimestrales habituales. En el 4T separa las retenciones (111, 115 y similares) de los
  modelos 130/131/303/309, que tienen vencimientos distintos.
- Lista de documentos por filas: añadir, quitar, editar y reordenar sin trabajar
  sobre un bloque de texto. Las notas adicionales se mantienen plegadas cuando no
  hacen falta.
- **Editor del documento tipo Word**: el texto predefinido se carga ya resuelto (con
  cliente, periodo y fecha) y se puede **editar libremente** — añadir líneas y espacios,
  cambiar palabras, poner negrita/cursiva, viñetas… Si no se ha tocado a mano, al cambiar
  los datos del formulario el texto se reescribe solo (la fecha sigue siendo automática);
  si se ha editado, no se pisa (avisa y deja reescribir a demanda). Botón «Restaurar texto
  de la plantilla».
- **«Guardar como predeterminado»**: convierte el texto que tengas en el editor en el
  texto base de ese tipo de aviso, para todos los futuros (p. ej. todos los trimestres).
  Al guardarlo se reinsertan automáticamente los comodines de cliente, periodo y fecha, de
  modo que esos datos se siguen rellenando solos; las listas y la tabla de plazos también
  se conservan como comodines. Se puede revisar/deshacer en Editar plantillas.
- **Documentación opcional reutilizable**: bloques de documentos con nombre (p. ej. «Venta
  de bienes inmuebles»), con una frase introductoria opcional y su propia lista, que se
  añaden o quitan con un clic en cualquier tipo de aviso. Se insertan como su propio
  párrafo y su propia lista (no se mezclan con la lista de documentos base). Se gestionan
  desde Herramientas → Documentación opcional.
- **Vista previa del PDF** como vista principal, idéntica al PDF final, con acceso
  directo a la edición de contenido y aviso visible si el texto no cabe en una
  sola página o si hay cambios del formulario pendientes de aplicar.
- Cabecera con el logo, colores de marca y pie de página fijo en todos los avisos.
- **Base de datos de clientes** (nombre, NIF, teléfono, email) con búsqueda por
  nombre o NIF, alta y edición rápida desde el aviso y buscador en la gestión de
  clientes. El NIF se rellena automáticamente en el aviso.
- **Generar para varios clientes**: el mismo aviso, incluidas las modificaciones
  manuales realizadas en el editor, una copia individual por cliente. Incluye
  búsqueda por nombre/NIF, evita destinatarios duplicados y permite elegir carpeta.
- **Historial reutilizable**: búsqueda por cliente, plantilla, periodo o fecha,
  acceso al PDF y acción «Crear otro igual» para recuperar los datos y el texto
  exactos del aviso guardado.
- **Editor de plantillas** para cambiar los textos desde la propia aplicación, sin tocar código.
- **Formato del documento** (Herramientas → Formato del documento…): fuente, tamaño de letra,
  interlineado y espacio entre párrafos configurables al estilo Word, con vista previa en
  vivo. Se guarda y se aplica a todos los avisos futuros.
- **Generar y guardar PDF** recuerda la carpeta elegida. Tras generarlo permite
  abrir el PDF, abrir la carpeta o conservar los datos y cambiar solo de cliente.
- **Comprobación de actualizaciones** contra los releases de GitHub (automática al abrir,
  o desde Ayuda → Buscar actualizaciones): descarga e instala la versión nueva con un clic.
  La consulta se hace en segundo plano (no congela la interfaz aunque la red vaya lenta).
- **Robustez**: registro de actividad y errores en `%APPDATA%\AvisosEMarin\avisos.log`
  (los fallos inesperados muestran un aviso claro en vez de cerrar la app en silencio),
  y escritura atómica de todos los datos (un corte de luz no corrompe clientes/plantillas).
- La ventana **recuerda su tamaño y la posición del separador** entre sesiones, y
  Herramientas → Abrir carpeta de datos da acceso directo a los archivos para copias
  de seguridad.

## Cálculo de plazos (AEAT)

En `avisos/templates.py` se calculan el primer vencimiento general y la fecha de
domiciliación de cada trimestre. Para 1T/2T/3T son, con carácter general, los días 20 y 15.
En el **4T** se distinguen dos grupos: retenciones hasta los días 20/15 de enero y modelos
130/131/303/309 hasta los días 30/25. Si una fecha inhábil lo requiere, se ajusta usando
fin de semana, festivos nacionales fijos y Viernes Santo.
**Importante:** solo cubre festivos nacionales — conviene revisar el calendario oficial de la
AEAT en fechas señaladas o con festivos locales de Murcia, que la propia AEAT sí tiene en
cuenta para estos cálculos.

## Estética / manual de estilo

Todo lo que define el estilo está centralizado en [`avisos/config.py`](avisos/config.py):
colores (verde `#2E4A3C`, dorado `#B8995A`) y datos del pie de página. La tipografía
(fuente, tamaño, interlineado y espacio entre párrafos) se guarda aparte, en
[`avisos/estilo.py`](avisos/estilo.py) (`%APPDATA%\AvisosEMarin\estilo.json`), y es
configurable por el usuario desde Herramientas → Formato del documento. Por defecto es
**Georgia** (fuente estándar de Windows); se descartó una fuente variable incrustada
porque algunas exportan mal el grosor —todo en negrita— al generar el PDF, aunque en
pantalla se vieran bien.

Para cambiar el logo, basta con dejar un archivo cuyo nombre empiece por `EM_logo`
en la carpeta `assets/`. Si pones un **PNG con fondo transparente** se usará ese
en lugar del JPG (queda más limpio sobre el folio blanco).

## Ejecutar en desarrollo

Requiere Python 3.11+.

```bat
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py
```

## Compilar el ejecutable (.exe)

```bat
build_exe.bat
```

Genera `dist\AvisosEMarin\AvisosEMarin.exe` (carpeta autocontenida, igual que el
Escáner de Fotos).

## Crear el instalador

1. Compila el .exe con `build_exe.bat`.
2. Abre `installer\AvisosEMarin.iss` con [Inno Setup](https://jrsoftware.org/isdl.php) y pulsa *Compile*.
3. El instalador queda en `dist_installer\`.

## Publicar una versión nueva (todo en uno)

```bat
.venv\Scripts\python scripts\release.py 1.7.0
```

Actualiza la versión en los dos sitios, ejecuta las pruebas (se detiene si fallan),
compila el .exe y el instalador, y crea el zip portable. Después solo queda el
commit/push y `gh release create`.

## Estructura

```
AvisosClientes/
├─ avisos/
│  ├─ config.py      # manual de estilo: colores, datos fijos, rutas
│  ├─ templates.py   # plantillas, motor de sustitución y overrides editables
│  ├─ render.py      # composición y export a PDF / vista previa
│  ├─ estilo.py      # fuente/tamaño/interlineado configurables (JSON)
│  ├─ clients.py     # base de datos de clientes (JSON)
│  ├─ history.py     # historial de avisos generados (JSON)
│  ├─ util.py        # nombre de archivo sugerido
│  ├─ ui/            # diálogos: clientes, lote, historial, editor de plantillas y formato
│  ├─ app.py         # ventana principal (PySide6)
│  └─ main.py        # arranque
├─ assets/           # logo e icono
├─ scripts/          # smoketest.py, test_full.py (pruebas de desarrollo)
├─ run.py            # lanzador en desarrollo
├─ AvisosEMarin.spec # PyInstaller
└─ installer/        # Inno Setup
```

Los datos del usuario (clientes, historial y plantillas personalizadas) se guardan en
`%APPDATA%\AvisosEMarin\`, fuera del programa, para que sobrevivan a las actualizaciones.

## Licencia

Código propio de Asesoría E. Marín.
