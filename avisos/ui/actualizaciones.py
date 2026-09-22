"""Descarga e instalacion de actualizaciones desde GitHub.

Tanto la consulta ("¿hay version nueva?") como la descarga se hacen en
un hilo aparte, para que la interfaz no se congele si la conexion va
lenta (especialmente en la comprobacion automatica del arranque).
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from .. import updater
from ..log import logger


class _HiloConsulta(QThread):
    resultado = Signal(object)  # VersionRemota | None

    def run(self) -> None:
        self.resultado.emit(updater.comprobar())


# Hilos de consulta en curso: se esperan al salir de la aplicacion para
# no destruir un QThread todavia vivo (provocaria un cierre abrupto).
_consultas_activas: list[_HiloConsulta] = []


def esperar_consultas(ms: int = 8000) -> None:
    for hilo in list(_consultas_activas) + list(_descargas_activas):
        hilo.wait(ms)


class _HiloDescarga(QThread):
    progreso = Signal(int)
    terminado = Signal(str)
    fallo = Signal(str)

    def __init__(self, act: updater.VersionRemota, destino: Path) -> None:
        super().__init__()
        self._act = act
        self._destino = destino

    def run(self) -> None:
        try:
            def notificar_progreso(valor: int) -> None:
                if self.isInterruptionRequested():
                    raise InterruptedError("Descarga cancelada")
                self.progreso.emit(valor)

            ruta = updater.preparar_instalacion(
                self._act, destino=self._destino,
                progreso=notificar_progreso,
            )
            self.terminado.emit(str(ruta))
        except Exception as e:
            self.fallo.emit(str(e))


_descargas_activas: list[_HiloDescarga] = []


def iniciar_instalador(ruta: str | Path) -> None:
    subprocess.Popen(
        [str(ruta), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS",
         "/RESTARTAPPLICATIONS"],
        close_fds=True,
    )


def comprobar_actualizaciones(parent, version_actual: str, silencioso: bool) -> None:
    """Comprueba si hay una version mas nueva en GitHub y ofrece instalarla.

    Si `silencioso` es True (comprobacion automatica al abrir), no dice
    nada si ya esta actualizado o si falla la conexion. La consulta se
    hace en segundo plano: la interfaz sigue respondiendo mientras tanto.
    """
    if hasattr(parent, "_actualizacion_estado"):
        parent._actualizacion_estado(updater.ESTADO_COMPROBANDO)
    hilo = _HiloConsulta()
    _consultas_activas.append(hilo)

    def _con_resultado(remota) -> None:
        if hilo in _consultas_activas:
            _consultas_activas.remove(hilo)
        hilo.deleteLater()
        _procesar_resultado(parent, version_actual, silencioso, remota)

    hilo.resultado.connect(_con_resultado)
    hilo.start()


def _procesar_resultado(parent, version_actual: str, silencioso: bool, remota) -> None:
    if remota is None:
        logger.info("Comprobacion de actualizaciones: sin respuesta (o sin red)")
        if not silencioso:
            QMessageBox.warning(parent, "Buscar actualizaciones",
                                 "No se ha podido comprobar si hay una versión nueva.\n"
                                 "Revisa tu conexión a internet.")
        if hasattr(parent, "_actualizacion_error"):
            parent._actualizacion_error("No se pudo contactar con el canal de actualizaciones")
        return
    if not updater.hay_actualizacion(version_actual, remota):
        if hasattr(parent, "_actualizacion_estado"):
            parent._actualizacion_estado(updater.ESTADO_INACTIVA)
        if not silencioso:
            QMessageBox.information(parent, "Buscar actualizaciones",
                                     f"Ya tienes la última versión (v{version_actual}).")
        return

    logger.info("Actualizacion disponible: %s (instalada v%s)", remota.tag, version_actual)
    if not silencioso:
        resp = QMessageBox.question(
            parent, "Actualización disponible",
            f"Hay una versión nueva disponible: {remota.tag} (tienes v{version_actual}).\n\n"
            "¿Descargarla y dejarla lista? Puedes instalarla ahora o al cerrar.",
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            if hasattr(parent, "_actualizacion_estado"):
                parent._actualizacion_estado(updater.ESTADO_INACTIVA)
            return

    destino = Path(tempfile.gettempdir()) / "AvisosEMarin" / "updates"
    progreso = None
    if not silencioso:
        progreso = QProgressDialog("Descargando actualización…", "Cancelar", 0, 100, parent)
        progreso.setWindowTitle("Actualizando")
        progreso.setMinimumDuration(0)
        progreso.setAutoClose(False)

    if hasattr(parent, "_actualizacion_estado"):
        parent._actualizacion_estado(updater.ESTADO_DESCARGANDO)
    hilo = _HiloDescarga(remota, destino)
    _descargas_activas.append(hilo)
    if progreso is not None:
        hilo.progreso.connect(progreso.setValue)

    def _al_terminar(ruta: str) -> None:
        if hilo in _descargas_activas:
            _descargas_activas.remove(hilo)
        if progreso is not None:
            progreso.close()
        if hasattr(parent, "_actualizacion_lista"):
            parent._actualizacion_lista(ruta)
        caja = QMessageBox(parent)
        caja.setWindowTitle("Actualización lista")
        caja.setText("La actualización está descargada y verificada. ¿Cuándo quieres instalarla?")
        ahora = caja.addButton("Reiniciar ahora", QMessageBox.AcceptRole)
        caja.addButton("Al cerrar", QMessageBox.ActionRole)
        caja.exec()
        if caja.clickedButton() is ahora and hasattr(parent, "_instalar_actualizacion_ahora"):
            parent._instalar_actualizacion_ahora()
        hilo.deleteLater()

    def _al_fallar(mensaje: str) -> None:
        if hilo in _descargas_activas:
            _descargas_activas.remove(hilo)
        if progreso is not None:
            progreso.close()
        if hasattr(parent, "_actualizacion_error"):
            parent._actualizacion_error(mensaje)
        if "SHA-256" in mensaje:
            detalle = (
                "La descarga no superó la comprobación de seguridad, incluso después "
                "de reintentarlo. No se ha instalado ningún archivo.\n\n"
                "Vuelve a intentarlo más tarde o descarga el instalador desde la página "
                "oficial de versiones en GitHub."
            )
        else:
            detalle = f"No se pudo descargar la actualización:\n{mensaje}"
        QMessageBox.critical(parent, "Error de actualización", detalle)
        hilo.deleteLater()

    hilo.terminado.connect(_al_terminar)
    hilo.fallo.connect(_al_fallar)
    if progreso is not None:
        progreso.canceled.connect(hilo.requestInterruption)
    hilo.start()
    if progreso is not None:
        progreso.exec()
