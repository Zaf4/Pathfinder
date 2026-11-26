"""Colours and stylesheet. Follows the system light/dark setting."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


@dataclass(frozen=True)
class Tokens:
    bg: str
    surface: str
    surface2: str
    border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_text: str
    accent_soft: str
    danger: str
    warn_bg: str
    warn_text: str
    pool: str
    pool_edge: str
    zone: str
    zone2: str
    dark: bool


LIGHT = Tokens(
    bg="#F4F6F8", surface="#FFFFFF", surface2="#F0F3F6", border="#DDE3E9", text="#16202A", muted="#5F6B78",
    accent="#0B7A8A", accent_hover="#09687A", accent_text="#FFFFFF", accent_soft="#E1F2F4",
    danger="#C62828", warn_bg="#FFF4E0", warn_text="#7A4B00",
    pool="#EAF6F8", pool_edge="#2C3E50", zone="#CFE7EC", zone2="#FFFFFF", dark=False,
)
DARK = Tokens(
    bg="#14181D", surface="#1C2228", surface2="#232A31", border="#313A44", text="#E8EDF2", muted="#9AA6B2",
    accent="#2BB3C4", accent_hover="#46C2D1", accent_text="#071318", accent_soft="#173A40",
    danger="#EF5350", warn_bg="#3A2E14", warn_text="#F5D48B",
    pool="#18303A", pool_edge="#B8C7D3", zone="#24485A", zone2="#18303A", dark=True,
)


def current() -> Tokens:
    hints = QGuiApplication.styleHints()
    try:
        return DARK if hints.colorScheme() == Qt.ColorScheme.Dark else LIGHT
    except AttributeError:  # Qt < 6.5
        return LIGHT


def palette(t: Tokens) -> QPalette:
    p = QPalette()
    c = QColor
    p.setColor(QPalette.Window, c(t.bg))
    p.setColor(QPalette.WindowText, c(t.text))
    p.setColor(QPalette.Base, c(t.surface))
    p.setColor(QPalette.AlternateBase, c(t.surface2))
    p.setColor(QPalette.Text, c(t.text))
    p.setColor(QPalette.Button, c(t.surface))
    p.setColor(QPalette.ButtonText, c(t.text))
    p.setColor(QPalette.Highlight, c(t.accent))
    p.setColor(QPalette.HighlightedText, c(t.accent_text))
    p.setColor(QPalette.ToolTipBase, c(t.surface))
    p.setColor(QPalette.ToolTipText, c(t.text))
    p.setColor(QPalette.PlaceholderText, c(t.muted))
    p.setColor(QPalette.Link, c(t.accent))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c(t.muted))
    return p


CHECK = (Path(__file__).parent / "assets" / "check.svg").as_posix()


def stylesheet(t: Tokens) -> str:
    return f"""
    QWidget {{ font-size: 13px; color: {t.text}; }}
    QMainWindow, QDialog {{ background: {t.bg}; }}
    QToolTip {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border}; padding: 6px; border-radius: 6px; }}

    #Sidebar {{ background: {t.surface}; border-right: 1px solid {t.border}; }}
    #AppTitle {{ font-size: 18px; font-weight: 700; }}
    #AppSubtitle {{ color: {t.muted}; font-size: 12px; }}

    #PageTitle {{ font-size: 22px; font-weight: 700; }}
    #PageSubtitle {{ color: {t.muted}; font-size: 13px; }}
    #SectionTitle {{ font-size: 14px; font-weight: 600; }}
    #Muted {{ color: {t.muted}; }}
    #Hint {{ color: {t.muted}; font-size: 12px; }}
    #BigNumber {{ font-size: 26px; font-weight: 700; }}
    #Error {{ color: {t.danger}; font-size: 12px; }}

    #Card {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 12px; }}
    #Banner {{ background: {t.warn_bg}; color: {t.warn_text}; border-radius: 8px; padding: 8px 12px; }}
    #Banner QLabel {{ color: {t.warn_text}; }}
    #InfoBanner {{ background: {t.accent_soft}; border-radius: 8px; padding: 8px 12px; }}

    QPushButton {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 8px;
        padding: 7px 14px; min-height: 18px;
    }}
    QPushButton:hover {{ background: {t.surface2}; }}
    QPushButton:pressed {{ background: {t.border}; }}
    QPushButton:disabled {{ color: {t.muted}; background: {t.surface2}; }}
    QPushButton#Primary {{
        background: {t.accent}; color: {t.accent_text}; border: 1px solid {t.accent}; font-weight: 600;
        padding: 9px 20px;
    }}
    QPushButton#Primary:hover {{ background: {t.accent_hover}; border-color: {t.accent_hover}; }}
    QPushButton#Primary:disabled {{ background: {t.border}; border-color: {t.border}; color: {t.muted}; }}
    QPushButton#Link {{ background: transparent; border: none; color: {t.accent}; padding: 2px 4px; }}
    QPushButton#Link:hover {{ text-decoration: underline; }}
    QPushButton#Strategy {{ text-align: left; padding: 8px 12px; }}
    QPushButton#Strategy:hover {{ border-color: {t.accent}; }}
    QPushButton#Strategy:checked {{ background: {t.accent_soft}; border: 2px solid {t.accent}; }}

    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 7px; padding: 5px 8px;
        selection-background-color: {t.accent}; selection-color: {t.accent_text};
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{ border: 2px solid {t.accent}; padding: 4px 7px; }}
    QLineEdit[invalid="true"] {{ border: 2px solid {t.danger}; padding: 4px 7px; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; border: none; }}
    QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{ width: 0; height: 0; }}
    QComboBox QAbstractItemView {{ background: {t.surface}; border: 1px solid {t.border}; selection-background-color: {t.accent_soft}; selection-color: {t.text}; }}

    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {t.border}; background: {t.surface}; }}
    QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.accent}; image: url("{CHECK}"); }}
    QCheckBox::indicator:hover {{ border-color: {t.accent}; }}
    QRadioButton {{ spacing: 8px; }}

    QTableView {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; gridline-color: transparent;
        alternate-background-color: {t.surface2}; selection-background-color: {t.accent_soft}; selection-color: {t.text};
    }}
    QTableView::item {{ padding: 4px 8px; border: none; }}
    QHeaderView::section {{
        background: {t.surface}; color: {t.muted}; border: none; border-bottom: 1px solid {t.border};
        padding: 6px 8px; font-weight: 600; font-size: 12px;
    }}
    QTableCornerButton::section {{ background: {t.surface}; border: none; }}

    QTabWidget::pane {{ border: none; }}
    QTabWidget::tab-bar {{ left: 0; }}
    QTabBar {{ background: transparent; qproperty-drawBase: 0; }}
    QTabBar::tab {{
        background: transparent; color: {t.muted}; padding: 8px 14px; margin-right: 4px;
        border-bottom: 2px solid transparent; font-weight: 600;
    }}
    QTabBar::tab:selected {{ color: {t.text}; border-bottom: 2px solid {t.accent}; }}
    QTabBar::tab:hover {{ color: {t.text}; }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle {{ background: {t.border}; border-radius: 3px; min-height: 30px; min-width: 30px; }}
    QScrollBar::handle:hover {{ background: {t.muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QProgressBar {{ background: {t.surface2}; border: none; border-radius: 6px; height: 12px; text-align: center; color: transparent; }}
    QProgressBar::chunk {{ background: {t.accent}; border-radius: 6px; }}
    QStatusBar {{ background: {t.surface}; border-top: 1px solid {t.border}; color: {t.muted}; }}
    QListWidget {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; }}
    QGroupBox {{ border: none; margin-top: 0; }}
    """
