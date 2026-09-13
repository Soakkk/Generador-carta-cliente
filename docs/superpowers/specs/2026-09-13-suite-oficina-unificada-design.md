# Generador de cartas dentro de la suite de oficina

Estado: aprobado por el usuario el 13 de septiembre de 2026.

## Objetivo

Unificar la interfaz de Avisos Asesoría E. Marín con Facturas a Aplifisa y acelerar la preparación repetitiva de cartas individuales y por lotes. La aplicación seguirá siendo PySide6 y conservará su editor y vista previa.

## Límites

- Facturas a Aplifisa es referencia de solo lectura; FocusNotch y repositorios de instaladores quedan fuera.
- Plantillas, textos resueltos, logo, paginación, formato del documento y PDF final son contratos inmutables.
- La mejora visual afecta únicamente a la interfaz de trabajo.
- Las automatizaciones no cambian un documento editado manualmente sin confirmación.

## Sistema visual compartido

Se adoptan los tokens de Facturas a Aplifisa: `#F5F8FC`, blanco, `#24384D`, `#5D7084`, `#DCE5F0`, `#326FA6`, `#19724E`, `#86500A` y `#B43737`, con Segoe UI Variable/Segoe UI.

Se conserva el reparto formulario/editor/vista previa, con barra superior clara, jerarquía de acciones, controles, estados y menús comunes. “Copiar texto” sigue siendo la acción primaria; guardar y abrir son acciones de cierre. El icono usa la forma común de la suite con un pictograma de carta.

## Automatización del flujo

1. Guardar un borrador completo del aviso activo y restaurarlo tras cierre, fallo o actualización, incluyendo selección de plantilla, cliente, documentos, extras y edición manual.
2. Añadir clientes recientes y favoritos con búsqueda por nombre o NIF y relleno desde el directorio local común.
3. Incorporar “Guardar y siguiente cliente”: genera con el mismo motor actual, registra el historial, conserva plantilla/periodo/documentación y limpia solo los datos personales necesarios.
4. Mejorar lotes con cola visible, progreso por cliente, cancelación segura, reintento de fallidos y resumen final. Un error no vuelve a generar los documentos correctos.
5. Recordar carpeta, modo de salida y configuración de una serie. Los nombres siguen usando `nombre_archivo` y `ruta_sin_colision` actuales.
6. Mantener un deshacer limitado para cambios de cliente, eliminación de documentos de la lista y limpieza de borrador.

## Directorio compartido de clientes

`%LOCALAPPDATA%\AsesoriaEMarin\Suite\clientes.json` mantiene nombre, NIF, dirección, IBAN, teléfono y email con procedencia y fecha por campo. La base actual se importa sin eliminarla. Las escrituras son atómicas y fusionan por NIF normalizado. Un conflicto se muestra para decidir y nunca pisa silenciosamente un valor reciente.

## Actualizaciones y publicación

La comprobación ocurre al arrancar y periódicamente. El instalador se descarga y valida en segundo plano. Antes de instalar se conserva el borrador; se puede reiniciar en el momento o dejar la actualización lista para el cierre. Inno Setup reemplaza la instalación y reabre la app.

El flujo de release pasa pruebas, sincroniza versiones, construye EXE/instalador, genera SHA-256 y publica en el canal configurado. La publicación deja de requerir una secuencia manual de commit + release.

## Errores y recuperación

Cada cliente de un lote tiene estado pendiente, generando, completado o fallido. Los fallos incluyen una explicación y una acción concreta. Los datos completados permanecen disponibles. Las plantillas personalizadas y el historial mantienen las escrituras atómicas actuales y se incluyen en copias rotativas.

## Verificación

- Mantener y ampliar `scripts/test_full.py` para sesión, lotes, cliente común y actualizaciones.
- Añadir fixtures y hashes que demuestren que los PDF y textos generados no cambian.
- Pruebas de UI para jerarquía, estados, teclado y distintos tamaños de ventana.
- Prueba de interrupción y reanudación de un lote.
- Construcción Windows del instalador antes de publicar.

