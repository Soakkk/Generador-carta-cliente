"""Sistema visual compartido por las aplicaciones de la suite de oficina.

Este módulo solo afecta a la interfaz Qt. El documento, logo, tipografía de
la carta, paginación y PDF siguen definidos en ``config``, ``estilo`` y
``render`` y no consumen estos tokens.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

from . import config

PAGE = "#F5F8FC"
CARD = "#FFFFFF"
SOFT = "#FAFCFE"
INK = "#24384D"
MUTED = "#5D7084"
BORDER = "#DCE5F0"
ACCENT = "#326FA6"
ACCENT_HOVER = "#285E90"
ACCENT_FAINT = "#EAF3FC"
SUCCESS = "#19724E"
WARNING = "#86500A"
DANGER = "#B43737"
FUENTE_UI = '"Segoe UI Variable", "Segoe UI", sans-serif'
CHEVRON = config.asset("chevron-down.svg").as_posix()

# Alias conservados para extensiones antiguas de la aplicación.
NAVY = ACCENT
NAVY_HOVER = ACCENT_HOVER

QSS = f"""
QWidget {{ color: {INK}; font-family: {FUENTE_UI}; font-size: 12px; }}
QMainWindow, QDialog, QMessageBox, QFileDialog {{ background: {PAGE}; }}
QMenuBar {{
    background: {CARD}; color: {MUTED}; border: none;
    padding: 0 10px; min-height: 28px;
}}
QMenuBar::item {{ padding: 6px 10px; border-radius: 3px; font-weight: 600; }}
QMenuBar::item:selected {{ background: {ACCENT_FAINT}; color: {ACCENT}; }}
QMenu {{ background: {CARD}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 8px 26px 8px 11px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT_FAINT}; color: {ACCENT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

QFrame#cabecera {{ background: {CARD}; border: none; border-bottom: 1px solid {BORDER}; }}
QLabel#marca {{ color: {INK}; font-size: 17px; font-weight: 600; }}
QLabel#marcaSubtitulo {{ color: {MUTED}; font-size: 11px; }}
QPushButton#cabeceraAccion {{
    background: transparent; color: {INK}; border: 1px solid transparent;
    padding: 7px 11px; font-weight: 500;
}}
QPushButton#cabeceraAccion:hover {{
    background: {ACCENT_FAINT}; color: {ACCENT}; border-color: {BORDER};
}}

QWidget#panelFormulario {{ background: transparent; border: none; }}
QWidget#panelDocumento {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#tituloSeccion {{ color: {INK}; font-size: 17px; font-weight: 600; }}
QLabel#textoSuave {{ color: {MUTED}; font-size: 11px; }}
QLabel#infoFecha {{
    color: {MUTED}; font-size: 11px; background: {ACCENT_FAINT};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 9px;
}}

QGroupBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 9px;
    margin-top: 12px; padding: 11px 10px 9px; font-weight: 600; color: {INK};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
QPushButton, QToolButton {{
    background: {CARD}; color: {INK}; border: 1px solid {BORDER};
    border-radius: 7px; padding: 7px 11px; font-weight: 500;
}}
QPushButton:hover, QToolButton:hover {{
    background: {ACCENT_FAINT}; border-color: {ACCENT}; color: {ACCENT};
}}
QPushButton:pressed, QToolButton:pressed {{ background: #DDEBFA; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid {ACCENT}; padding: 6px 10px; }}
QPushButton:disabled, QToolButton:disabled {{
    background: {SOFT}; color: {MUTED}; border-color: {BORDER};
}}
QPushButton#primario {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
QPushButton#primario:hover {{ background: {ACCENT_HOVER}; color: white; }}
QPushButton#exito {{ background: {SUCCESS}; color: white; border-color: {SUCCESS}; }}
QPushButton#peligro {{ color: {DANGER}; }}
QPushButton#peligro:hover {{ border-color: {DANGER}; color: {DANGER}; background: #FFF0F0; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit, QListWidget {{
    background: {CARD}; color: {INK}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 7px 9px; min-height: 22px;
    selection-background-color: {ACCENT}; selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDateEdit:focus, QListWidget:focus {{ border: 2px solid {ACCENT}; }}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDateEdit:disabled, QListWidget:disabled {{
    background: {SOFT}; color: {MUTED}; border-color: {BORDER};
}}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT_FAINT}; selection-color: {ACCENT};
    outline: 0; padding: 5px;
}}
QComboBox::drop-down {{ width: 32px; border: none; border-left: 1px solid {BORDER}; }}
QComboBox::down-arrow {{ image: url("{CHEVRON}"); width: 12px; height: 8px; }}
QComboBox QAbstractItemView::item {{ min-height: 32px; padding: 7px 10px; }}
QPushButton#segmento {{ border-radius: 5px; padding: 7px 10px; background: {SOFT}; }}
QPushButton#segmento:checked {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
QToolButton#etiquetaOpcional {{ padding: 7px 10px; text-align: left; background: {SOFT}; }}
QToolButton#etiquetaOpcional:checked {{
    background: #E7F5EE; color: {SUCCESS}; border-color: {SUCCESS};
}}

QListWidget#listaDocumentos::item {{ padding: 7px 5px; border-bottom: 1px solid {BORDER}; }}
QListWidget#listaDocumentos::item:selected {{ background: {ACCENT_FAINT}; color: {INK}; }}
QTextEdit#editorDocumento {{ padding: 22px; }}
QTabWidget::pane {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; }}
QTabBar::tab {{
    background: {PAGE}; color: {MUTED}; border: 1px solid {BORDER};
    padding: 8px 14px; margin-right: 2px; border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{ background: {CARD}; color: {ACCENT}; font-weight: 600; }}

QTableWidget {{
    background: {CARD}; alternate-background-color: {SOFT};
    border: 1px solid {BORDER}; border-radius: 6px; gridline-color: {BORDER};
    selection-background-color: {ACCENT_FAINT}; selection-color: {INK};
}}
QHeaderView::section {{
    background: {PAGE}; color: {MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 8px 6px; font-weight: 500;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSplitter::handle {{ background: {PAGE}; width: 8px; }}
QFrame#barraAcciones {{ background: {CARD}; border-top: 1px solid {BORDER}; }}
QLabel#rutaDestino {{ color: {ACCENT}; font-weight: 600; }}
QLabel#estadoListo {{ color: {SUCCESS}; font-weight: 600; }}
QLabel#estadoAviso {{ color: {WARNING}; font-weight: 600; }}
QLabel#estadoError {{ color: {DANGER}; font-weight: 600; }}
QProgressBar {{
    background: #E8EDF4; border: none; border-radius: 3px;
    min-height: 9px; max-height: 9px; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

QScrollBar:vertical {{ background: #EEF3F8; width: 14px; margin: 2px; border-radius: 6px; }}
QScrollBar::handle:vertical {{
    background: #AFC0D1; border: 2px solid #EEF3F8; border-radius: 5px; min-height: 48px;
}}
QScrollBar::handle:vertical:hover {{ background: #7F93A8; }}
QScrollBar:horizontal {{ background: #EEF3F8; height: 14px; margin: 2px; border-radius: 6px; }}
QScrollBar::handle:horizontal {{
    background: #AFC0D1; border: 2px solid #EEF3F8; border-radius: 5px; min-width: 48px;
}}
QScrollBar::handle:horizontal:hover {{ background: #7F93A8; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {CARD}; color: {INK}; border: 1px solid {BORDER}; padding: 7px 9px; }}
"""


def aplicar_tema(app) -> None:
    app.setStyle("Fusion")
    familias = set(QFontDatabase.families())
    familia = "Segoe UI Variable" if "Segoe UI Variable" in familias else "Segoe UI"
    app.setFont(QFont(familia, 10))
    paleta = app.palette()
    rol = QPalette.ColorRole
    paleta.setColor(rol.Window, QColor(PAGE))
    paleta.setColor(rol.WindowText, QColor(INK))
    paleta.setColor(rol.Base, QColor(CARD))
    paleta.setColor(rol.AlternateBase, QColor(SOFT))
    paleta.setColor(rol.Text, QColor(INK))
    paleta.setColor(rol.Button, QColor(CARD))
    paleta.setColor(rol.ButtonText, QColor(INK))
    paleta.setColor(rol.Highlight, QColor(ACCENT))
    paleta.setColor(rol.HighlightedText, QColor(CARD))
    paleta.setColor(rol.PlaceholderText, QColor(MUTED))
    app.setPalette(paleta)
    app.setStyleSheet(QSS)
