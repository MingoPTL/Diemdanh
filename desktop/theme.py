"""
desktop/theme.py — Hệ thống Theme Dark Mode Premium cho Desktop App
Bảng màu Slate/Blue hiện đại, font Inter/Segoe UI, glassmorphism cards
"""

# ── Bảng màu chính ────────────────────────────────────────────────────────────
COLORS = {
    # Nền
    "bg_primary":       "#0F172A",   # Slate-900 (nền chính)
    "bg_secondary":     "#1E293B",   # Slate-800 (nền card/panel)
    "bg_tertiary":      "#334155",   # Slate-700 (nền hover/input)
    "bg_elevated":      "#1A2332",   # Nền card nổi

    # Viền
    "border":           "#334155",   # Slate-700
    "border_light":     "rgba(255, 255, 255, 0.08)",
    "border_focus":     "#3B82F6",   # Blue-500

    # Chữ
    "text_primary":     "#F8FAFC",   # Slate-50
    "text_secondary":   "#94A3B8",   # Slate-400
    "text_muted":       "#64748B",   # Slate-500
    "text_accent":      "#38BDF8",   # Sky-400

    # Accent
    "blue":             "#3B82F6",   # Blue-500
    "blue_hover":       "#2563EB",   # Blue-600
    "blue_light":       "#60A5FA",   # Blue-400
    "green":            "#10B981",   # Emerald-500
    "green_light":      "#34D399",   # Emerald-400
    "yellow":           "#F59E0B",   # Amber-500
    "yellow_light":     "#FBBF24",   # Amber-400
    "red":              "#EF4444",   # Red-500
    "red_light":        "#F87171",   # Red-400
    "purple":           "#8B5CF6",   # Violet-500
    "orange":           "#F97316",   # Orange-500
    "orange_light":     "#FB923C",   # Orange-400

    # Trạng thái
    "present_bg":       "rgba(16, 185, 129, 0.15)",
    "present_text":     "#34D399",
    "present_border":   "rgba(16, 185, 129, 0.4)",
    "late_bg":          "rgba(245, 158, 11, 0.15)",
    "late_text":        "#FBBF24",
    "late_border":      "rgba(245, 158, 11, 0.4)",
    "absent_bg":        "rgba(239, 68, 68, 0.15)",
    "absent_text":      "#F87171",
    "absent_border":    "rgba(239, 68, 68, 0.4)",

    # Badges loại lớp
    "theory_bg":        "rgba(59, 130, 246, 0.15)",
    "theory_text":      "#60A5FA",
    "theory_border":    "rgba(59, 130, 246, 0.3)",
    "practice_bg":      "rgba(16, 185, 129, 0.15)",
    "practice_text":    "#34D399",
    "practice_border":  "rgba(16, 185, 129, 0.3)",
}

# ── Font ──────────────────────────────────────────────────────────────────────
FONT_FAMILY = "'Segoe UI', 'Inter', 'Roboto', 'Helvetica Neue', Arial, sans-serif"
FONT_SIZE_XS = 11
FONT_SIZE_SM = 12
FONT_SIZE_BASE = 13
FONT_SIZE_MD = 14
FONT_SIZE_LG = 16
FONT_SIZE_XL = 20
FONT_SIZE_2XL = 26
FONT_SIZE_3XL = 32

# ── Kích thước ────────────────────────────────────────────────────────────────
BORDER_RADIUS_SM = 6
BORDER_RADIUS_MD = 10
BORDER_RADIUS_LG = 14
BORDER_RADIUS_XL = 18
BORDER_RADIUS_ROUND = 9999

SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_2XL = 32


def get_main_stylesheet() -> str:
    """Trả về stylesheet QSS toàn cục cho Dark Mode Premium."""
    return f"""
    /* ═══════════════════════════════════════════════════════════════════════════
       GLOBAL BASE
       ═══════════════════════════════════════════════════════════════════════════ */
    * {{
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_BASE}px;
    }}

    QMainWindow {{
        background-color: {COLORS['bg_primary']};
    }}

    QWidget {{
        background-color: {COLORS['bg_primary']};
        color: {COLORS['text_primary']};
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       TAB WIDGET (Sidebar Navigation)
       ═══════════════════════════════════════════════════════════════════════════ */
    QTabWidget::pane {{
        border: none;
        background-color: {COLORS['bg_primary']};
    }}

    QTabBar {{
        background-color: {COLORS['bg_secondary']};
    }}

    QTabBar::tab {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_secondary']};
        padding: 12px 20px;
        border: none;
        border-bottom: 3px solid transparent;
        font-size: {FONT_SIZE_MD}px;
        font-weight: 500;
        min-width: 130px;
    }}

    QTabBar::tab:hover {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_primary']};
    }}

    QTabBar::tab:selected {{
        background-color: {COLORS['bg_primary']};
        color: {COLORS['blue_light']};
        border-bottom: 3px solid {COLORS['blue']};
        font-weight: 600;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       BUTTONS
       ═══════════════════════════════════════════════════════════════════════════ */
    QPushButton {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_MD}px;
        padding: 8px 18px;
        font-size: {FONT_SIZE_BASE}px;
        font-weight: 500;
        min-height: 32px;
    }}

    QPushButton:hover {{
        background-color: {COLORS['blue']};
        border-color: {COLORS['blue']};
        color: white;
    }}

    QPushButton:pressed {{
        background-color: {COLORS['blue_hover']};
    }}

    QPushButton:disabled {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_muted']};
        border-color: {COLORS['border']};
    }}

    QPushButton#btn_primary {{
        background-color: {COLORS['blue']};
        color: white;
        border: none;
        font-weight: 600;
    }}

    QPushButton#btn_primary:hover {{
        background-color: {COLORS['blue_hover']};
    }}

    QPushButton#btn_success {{
        background-color: {COLORS['green']};
        color: white;
        border: none;
        font-weight: 600;
    }}

    QPushButton#btn_success:hover {{
        background-color: #059669;
    }}

    QPushButton#btn_danger {{
        background-color: {COLORS['red']};
        color: white;
        border: none;
        font-weight: 600;
    }}

    QPushButton#btn_danger:hover {{
        background-color: #DC2626;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       INPUT FIELDS
       ═══════════════════════════════════════════════════════════════════════════ */
    QLineEdit, QSpinBox, QTimeEdit, QDateEdit {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 8px 12px;
        font-size: {FONT_SIZE_BASE}px;
        selection-background-color: {COLORS['blue']};
    }}

    QLineEdit:focus, QSpinBox:focus, QTimeEdit:focus, QDateEdit:focus {{
        border-color: {COLORS['border_focus']};
    }}

    QLineEdit:disabled {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_muted']};
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       COMBOBOX (Dropdown)
       ═══════════════════════════════════════════════════════════════════════════ */
    QComboBox {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 8px 12px;
        font-size: {FONT_SIZE_BASE}px;
        min-height: 28px;
    }}

    QComboBox:hover {{
        border-color: {COLORS['border_focus']};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 30px;
        border-left: 1px solid {COLORS['border']};
        border-top-right-radius: {BORDER_RADIUS_SM}px;
        border-bottom-right-radius: {BORDER_RADIUS_SM}px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        selection-background-color: {COLORS['blue']};
        selection-color: white;
        outline: none;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       TABLE
       ═══════════════════════════════════════════════════════════════════════════ */
    QTableWidget, QTableView {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_MD}px;
        gridline-color: {COLORS['border']};
        selection-background-color: rgba(59, 130, 246, 0.25);
        selection-color: {COLORS['text_primary']};
        alternate-background-color: {COLORS['bg_elevated']};
        font-size: {FONT_SIZE_SM}px;
    }}

    QHeaderView::section {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_secondary']};
        border: none;
        border-right: 1px solid {COLORS['border']};
        border-bottom: 1px solid {COLORS['border']};
        padding: 8px 12px;
        font-weight: 600;
        font-size: {FONT_SIZE_SM}px;
        text-transform: uppercase;
    }}

    QTableWidget::item {{
        padding: 6px 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       SCROLLBAR
       ═══════════════════════════════════════════════════════════════════════════ */
    QScrollBar:vertical {{
        background: {COLORS['bg_primary']};
        width: 10px;
        border-radius: 5px;
    }}

    QScrollBar::handle:vertical {{
        background: {COLORS['bg_tertiary']};
        min-height: 40px;
        border-radius: 5px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {COLORS['text_muted']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: {COLORS['bg_primary']};
        height: 10px;
        border-radius: 5px;
    }}

    QScrollBar::handle:horizontal {{
        background: {COLORS['bg_tertiary']};
        min-width: 40px;
        border-radius: 5px;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       LABELS
       ═══════════════════════════════════════════════════════════════════════════ */
    QLabel {{
        color: {COLORS['text_primary']};
        background: transparent;
    }}

    QLabel#label_title {{
        font-size: {FONT_SIZE_2XL}px;
        font-weight: 700;
        color: {COLORS['text_primary']};
    }}

    QLabel#label_subtitle {{
        font-size: {FONT_SIZE_LG}px;
        font-weight: 600;
        color: {COLORS['text_accent']};
    }}

    QLabel#label_section {{
        font-size: {FONT_SIZE_LG}px;
        font-weight: 700;
        color: {COLORS['text_accent']};
        padding-left: 12px;
        border-left: 4px solid {COLORS['blue']};
    }}

    QLabel#label_muted {{
        color: {COLORS['text_muted']};
        font-size: {FONT_SIZE_SM}px;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       GROUP BOX (Card-like panels)
       ═══════════════════════════════════════════════════════════════════════════ */
    QGroupBox {{
        background-color: {COLORS['bg_secondary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_LG}px;
        margin-top: 16px;
        padding: 20px 16px 16px 16px;
        font-size: {FONT_SIZE_MD}px;
        font-weight: 600;
        color: {COLORS['text_accent']};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background-color: {COLORS['bg_secondary']};
        border-radius: {BORDER_RADIUS_SM}px;
        color: {COLORS['text_accent']};
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       PROGRESS BAR
       ═══════════════════════════════════════════════════════════════════════════ */
    QProgressBar {{
        background-color: {COLORS['bg_tertiary']};
        border: none;
        border-radius: {BORDER_RADIUS_SM}px;
        text-align: center;
        color: {COLORS['text_primary']};
        font-weight: 600;
        font-size: {FONT_SIZE_SM}px;
        min-height: 22px;
    }}

    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {COLORS['blue']}, stop:1 {COLORS['green']});
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       CHECKBOX & RADIO
       ═══════════════════════════════════════════════════════════════════════════ */
    QCheckBox {{
        color: {COLORS['text_primary']};
        spacing: 8px;
        font-size: {FONT_SIZE_BASE}px;
        background: transparent;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {COLORS['border']};
        border-radius: 4px;
        background-color: {COLORS['bg_tertiary']};
    }}

    QCheckBox::indicator:checked {{
        background-color: {COLORS['blue']};
        border-color: {COLORS['blue']};
    }}

    QRadioButton {{
        color: {COLORS['text_primary']};
        spacing: 8px;
        font-size: {FONT_SIZE_BASE}px;
        background: transparent;
    }}

    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {COLORS['border']};
        border-radius: 9px;
        background-color: {COLORS['bg_tertiary']};
    }}

    QRadioButton::indicator:checked {{
        background-color: {COLORS['blue']};
        border-color: {COLORS['blue']};
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       LIST WIDGET
       ═══════════════════════════════════════════════════════════════════════════ */
    QListWidget {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_MD}px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 8px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }}

    QListWidget::item:hover {{
        background-color: {COLORS['bg_tertiary']};
    }}

    QListWidget::item:selected {{
        background-color: rgba(59, 130, 246, 0.25);
        color: {COLORS['text_primary']};
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       SPLITTER
       ═══════════════════════════════════════════════════════════════════════════ */
    QSplitter::handle {{
        background-color: {COLORS['border']};
    }}

    QSplitter::handle:horizontal {{
        width: 2px;
    }}

    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       TOOLTIP
       ═══════════════════════════════════════════════════════════════════════════ */
    QToolTip {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 6px 10px;
        font-size: {FONT_SIZE_SM}px;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       STATUS BAR
       ═══════════════════════════════════════════════════════════════════════════ */
    QStatusBar {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_muted']};
        border-top: 1px solid {COLORS['border']};
        font-size: {FONT_SIZE_SM}px;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       MENU BAR
       ═══════════════════════════════════════════════════════════════════════════ */
    QMenuBar {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_primary']};
        border-bottom: 1px solid {COLORS['border']};
    }}

    QMenuBar::item {{
        padding: 6px 14px;
        background: transparent;
    }}

    QMenuBar::item:selected {{
        background-color: {COLORS['bg_tertiary']};
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QMenu {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QMenu::item {{
        padding: 8px 24px;
    }}

    QMenu::item:selected {{
        background-color: {COLORS['blue']};
        color: white;
    }}

    /* ═══════════════════════════════════════════════════════════════════════════
       TEXT EDIT
       ═══════════════════════════════════════════════════════════════════════════ */
    QTextEdit, QPlainTextEdit {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 8px;
        font-size: {FONT_SIZE_BASE}px;
    }}
    """


def get_metric_card_style(accent_color: str = None) -> str:
    """Trả về style inline cho Metric Card với hiệu ứng glassmorphism."""
    accent = accent_color or COLORS['blue']
    return f"""
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {COLORS['bg_secondary']}, stop:1 {COLORS['bg_elevated']});
        border: 1px solid {COLORS['border']};
        border-left: 4px solid {accent};
        border-radius: {BORDER_RADIUS_LG}px;
        padding: 16px 20px;
    """


def get_session_banner_style(is_active: bool = True) -> str:
    """Trả về style cho banner trạng thái buổi điểm danh."""
    if is_active:
        return f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS['bg_secondary']}, stop:1 rgba(16, 185, 129, 0.08));
            border: 1px solid {COLORS['present_border']};
            border-radius: {BORDER_RADIUS_LG}px;
            padding: 14px 20px;
        """
    return f"""
        background: {COLORS['bg_secondary']};
        border: 1px solid {COLORS['border']};
        border-radius: {BORDER_RADIUS_LG}px;
        padding: 14px 20px;
    """


def get_light_stylesheet() -> str:
    """Trả về stylesheet QSS cho Light Mode."""
    return f"""
    * {{
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_BASE}px;
    }}
    QMainWindow, QWidget {{
        background-color: #F8FAFC;
        color: #0F172A;
    }}
    QTabWidget::pane {{
        border: none;
        background-color: #F8FAFC;
    }}
    QTabBar {{
        background-color: #E2E8F0;
    }}
    QTabBar::tab {{
        background-color: #E2E8F0;
        color: #475569;
        padding: 12px 20px;
        border: none;
        border-bottom: 3px solid transparent;
        font-size: {FONT_SIZE_MD}px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        background-color: #FFFFFF;
        color: #2563EB;
        border-bottom: 3px solid #2563EB;
        font-weight: 600;
    }}
    QPushButton {{
        background-color: #E2E8F0;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        border-radius: {BORDER_RADIUS_MD}px;
        padding: 8px 18px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: #3B82F6;
        color: white;
    }}
    QPushButton#btn_primary {{
        background-color: #2563EB;
        color: white;
    }}
    QPushButton#btn_primary:hover {{
        background-color: #1D4ED8;
    }}
    QPushButton#btn_success {{
        background-color: #059669;
        color: white;
    }}
    QPushButton#btn_danger {{
        background-color: #DC2626;
        color: white;
    }}
    QLineEdit, QComboBox, QSpinBox {{
        background-color: #FFFFFF;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        border-radius: {BORDER_RADIUS_SM}px;
        padding: 8px 12px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: #2563EB;
    }}
    QTableWidget {{
        background-color: #FFFFFF;
        alternate-background-color: #F1F5F9;
        border: 1px solid #E2E8F0;
        gridline-color: #E2E8F0;
    }}
    QHeaderView::section {{
        background-color: #E2E8F0;
        color: #0F172A;
        padding: 10px;
        border: none;
        font-weight: 600;
    }}
    QTableWidget::item {{
        color: #0F172A;
    }}
    QStatusBar {{
        background-color: #E2E8F0;
        color: #475569;
    }}
    """

