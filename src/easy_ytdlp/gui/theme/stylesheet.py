"""QSS template filled from the design tokens."""

from string import Template

from easy_ytdlp.gui.theme import icons
from easy_ytdlp.gui.theme import tokens as t
from easy_ytdlp.gui.theme.tokens import Tokens

# Widgets opt into variants with dynamic properties, e.g. button.setProperty("variant", "primary").
_TEMPLATE = Template(
    """
* {
    font-family: "$font", "$fallback";
    font-size: ${body}px;
    color: $foreground;
}
QMainWindow, QDialog, #Page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {
    background: $background;
}
QToolTip {
    background: $surface;
    color: $foreground;
    border: 1px solid $border;
    padding: 4px 8px;
}

/* Sidebar */
#Sidebar {
    background: $surface;
    border-right: 1px solid $border;
}
#SidebarTitle {
    font-size: ${section}px;
    font-weight: 600;
    padding: 4px 8px 12px 8px;
}
#SidebarButton {
    text-align: left;
    padding: 8px 12px;
    border: none;
    border-radius: ${radius}px;
    background: transparent;
    min-height: ${control}px;
}
#SidebarButton:hover { background: $surface_muted; }
#SidebarButton:checked {
    background: $selection;
    color: $foreground;
    font-weight: 600;
}
#SidebarButton:focus { outline: none; border: 2px solid $primary; }
#Badge {
    background: $primary;
    color: $on_primary;
    border-radius: 9px;
    padding: 0 6px;
    font-size: ${caption}px;
    font-weight: 600;
    min-width: 6px;
}
#AccentBadge {
    background: $accent;
    color: $on_accent;
    border-radius: 9px;
    padding: 2px 8px;
    font-size: ${caption}px;
    font-weight: 600;
}

/* Text */
#PageTitle { font-size: ${title}px; font-weight: 600; }
#SectionTitle { font-size: ${section}px; font-weight: 600; }
#Muted, #Caption { color: $muted_foreground; }
#Caption { font-size: ${caption}px; }
#ErrorText { color: $destructive; }
#SuccessText { color: $success; }
#WarningText { color: $warning; }

/* Cards */
#Card {
    background: $surface;
    border: 1px solid $border;
    border-radius: ${card_radius}px;
}
#Banner {
    background: $surface;
    border: 1px solid $warning;
    border-radius: ${card_radius}px;
}

/* Inputs */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit {
    background: $surface_muted;
    border: 1px solid $border;
    border-radius: ${radius}px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: $primary;
    selection-color: $on_primary;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid $primary;
}
QLineEdit[invalid="true"] { border: 2px solid $destructive; }
QLineEdit:disabled, QComboBox:disabled { color: $muted_foreground; }
#UrlInput { font-size: 16px; min-height: 30px; padding: 6px 12px; }
#Console, #CommandInput, #CommandView {
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 13px;
}
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: url($arrow_down); width: 14px; height: 14px; }
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border;
    selection-background-color: $selection;
    selection-color: $foreground;
    outline: none;
}

/* Buttons */
QPushButton, QToolButton {
    background: $surface;
    border: 1px solid $border;
    border-radius: ${radius}px;
    padding: 6px 14px;
    min-height: 20px;
}
QPushButton:hover, QToolButton:hover { background: $surface_muted; }
QPushButton:focus, QToolButton:focus { border: 2px solid $primary; }
QPushButton:disabled, QToolButton:disabled { color: $muted_foreground; }
QPushButton[variant="primary"] {
    background: $primary;
    color: $on_primary;
    border: 1px solid $primary;
    font-weight: 600;
    min-height: 24px;
}
QPushButton[variant="primary"]:hover { background: $primary_hover; }
QPushButton[variant="primary"]:focus { border: 2px solid $foreground; }
QPushButton[variant="primary"]:disabled {
    background: $border;
    border-color: $border;
    color: $muted_foreground;
}
QPushButton[variant="destructive"] { color: $destructive; }
QPushButton[variant="ghost"], QToolButton[variant="ghost"] {
    background: transparent;
    border: 1px solid transparent;
}
QToolButton[variant="ghost"] { padding: 6px; }
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover {
    background: $surface_muted;
}
QPushButton[variant="ghost"]:focus, QToolButton[variant="ghost"]:focus {
    border: 2px solid $primary;
}

/* Segmented control */
#Segmented {
    background: $surface_muted;
    border: 1px solid $border;
    border-radius: ${radius}px;
}
#Segmented QPushButton {
    border: none;
    background: transparent;
    padding: 6px 16px;
}
#Segmented QPushButton:checked {
    background: $surface;
    font-weight: 600;
    border: 1px solid $border;
}
#Segmented QPushButton:focus { border: 2px solid $primary; }

/* Progress */
QProgressBar {
    background: $surface_muted;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    font-size: 1px;
    color: transparent;
}
QProgressBar::chunk { background: $primary; border-radius: 4px; }
QProgressBar[state="failed"]::chunk { background: $destructive; }
QProgressBar[state="done"]::chunk { background: $success; }

/* State chips */
#Chip {
    border-radius: 10px;
    padding: 2px 8px;
    font-size: ${caption}px;
    font-weight: 600;
    background: $surface_muted;
    color: $muted_foreground;
}
#Chip[state="downloading"], #Chip[state="processing"] { color: $primary; }
#Chip[state="done"] { color: $success; }
#Chip[state="failed"] { color: $destructive; }
#Chip[state="cancelled"] { color: $muted_foreground; }

/* Lists and scroll bars */
QListWidget, QTreeWidget, QTableWidget {
    background: $surface;
    border: 1px solid $border;
    border-radius: ${radius}px;
    outline: none;
}
QListWidget::item, QTreeWidget::item { padding: 4px; }
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
    background: $selection;
    color: $foreground;
}
QHeaderView::section {
    background: $surface_muted;
    border: none;
    border-bottom: 1px solid $border;
    padding: 4px 8px;
    font-weight: 600;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 24px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: $border; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QCheckBox, QRadioButton { spacing: 8px; }
QCheckBox:focus, QRadioButton:focus { color: $primary; }
QGroupBox {
    border: 1px solid $border;
    border-radius: ${card_radius}px;
    margin-top: 14px;
    padding: 12px;
    background: $surface;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    font-weight: 600;
}

#Toast {
    background: $foreground;
    color: $background;
    border-radius: ${radius}px;
    padding: 8px 16px;
}
"""
)


def build(tokens: Tokens) -> str:
    return _TEMPLATE.substitute(
        tokens.as_dict(),
        arrow_down=icons.icon_file("chevron-down", tokens.muted_foreground),
        font=t.FONT_FAMILY,
        fallback=t.FALLBACK_FONT,
        body=t.FONT_BODY,
        caption=t.FONT_CAPTION,
        section=t.FONT_SECTION,
        title=t.FONT_TITLE,
        radius=t.RADIUS_CONTROL,
        card_radius=t.RADIUS_CARD,
        control=t.CONTROL_HEIGHT,
    )
