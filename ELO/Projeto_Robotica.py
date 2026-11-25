import math
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRect, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from . import aegis_config
    from .robot_view import RobotArmView
    from .camera_panel import CameraPanel
    from .focus_overlay import CameraFocusOverlay
except ImportError:
    import aegis_config
    from robot_view import RobotArmView
    from camera_panel import CameraPanel
    from focus_overlay import CameraFocusOverlay


# Interface AEGIS (tela). Este arquivo não envia comandos de movimento ao RTDE;
# o controle dos robôs fica em AEGIS_RTDE.py.
STYLE = """
QWidget { background:#06140F; color:#F0F6F1; font-family:'Segoe UI'; font-size:14px; }
QFrame#sidebar { background:#04100C; border:1px solid #173A28; border-radius:20px; }
QFrame#brandMark { background:#0B2418; border:2px solid #8EEA32; border-radius:21px; }
QFrame#card { background:#091B13; border:1px solid #214832; border-radius:17px; }
QFrame#softPanel { background:#0A2117; border:1px solid #214832; border-radius:13px; }
QFrame#metricTile { background:#0D281B; border:1px solid #244B33; border-radius:11px; }
QFrame#heroCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #071B12,stop:0.58 #0C2B1A,stop:1 #174225); border:1px solid #376D3B; border-radius:20px; }
QFrame#homeTile { background:#0A2016; border:1px solid #2A5735; border-radius:15px; }
QFrame#pageHeader { background:transparent; border-bottom:1px solid #1D3D2A; }
QTabWidget::pane { background:#081A12; border:1px solid #214832; border-radius:12px; top:-1px; }
QTabBar::tab { background:#0A2117; color:#A5BBA9; padding:10px 17px; margin-right:5px; border:1px solid #244B33; border-radius:9px 9px 0 0; font-weight:650; }
QTabBar::tab:selected { background:#244C2A; color:#B5FF5B; border-color:#5E9E36; }
QSplitter::handle:vertical { background:#1E412B; height:8px; border-radius:4px; }
QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; border:0; }
QLabel { background:transparent; }
QLabel#pageTitle { font-size:28px; font-weight:750; color:#F4F8F3; }
QLabel#brand { font-size:25px; font-weight:800; color:#F4F8F3; letter-spacing:2px; }
QLabel#brandGlyph { color:#A2F33B; font-size:24px; font-weight:700; }
QLabel#sideSection { color:#789585; font-size:10px; font-weight:700; letter-spacing:1px; padding:8px 10px 2px; }
QLabel#sideMuted { color:#9FB5A5; }
QLabel#robotName { font-size:21px; font-weight:700; color:#F3F7F2; }
QLabel#sectionTitle { font-size:14px; font-weight:700; color:#EAF4E8; }
QLabel#metricCaption { color:#A2B8A7; font-size:12px; font-weight:600; }
QLabel#metricValue { color:#F1F7EF; font-size:15px; font-weight:700; }
QLabel#muted { color:#A0B5A5; }
QLabel#badge { background:#123522; color:#B5FF5B; border:1px solid #28633C; border-radius:11px; padding:7px 12px; font-weight:700; }
QLabel#roleBadge { background:#123522; color:#A7F144; border:1px solid #28633C; border-radius:10px; padding:6px 10px; font-weight:700; }
QLabel#statusValue { font-size:18px; font-weight:700; color:#F2F7F1; }
QLabel#heroTitle { color:white; font-size:32px; font-weight:750; }
QLabel#heroCopy { color:#D5E6D7; font-size:14px; }
QLabel#heroEyebrow { color:#A9F046; font-size:11px; font-weight:750; letter-spacing:1.4px; }
QLabel#modelPlaceholder { background:#0C2117; color:#A0B5A5; border:1px dashed #386544; border-radius:12px; padding:18px; }
QPushButton { background:#10271A; color:#E8F2E8; border:1px solid #31553A; border-radius:10px; padding:10px 14px; font-weight:650; }
QPushButton:hover { background:#173821; border-color:#74C83A; }
QPushButton:disabled { background:#0A1911; color:#637868; border-color:#1B3524; }
QPushButton#nav { text-align:left; color:#B6C7BA; background:transparent; border:0; border-radius:9px; padding:11px 12px; }
QPushButton#nav:hover { background:#10291A; color:#F4F8F3; }
QPushButton#nav:checked { background:#28562B; color:#C0FF67; border:1px solid #5E9E36; }
QPushButton#primary { background:#91EA32; color:#10200D; border:0; font-weight:750; }
QPushButton#primary:hover { background:#A5F54A; }
QPushButton#heroButton { background:#9AF13A; color:#11210D; border:0; border-radius:12px; padding:12px 18px; font-weight:750; }
QPushButton#heroButton:hover { background:#B0FF5E; }
QPushButton#tileButton { text-align:left; background:transparent; border:0; color:#A9F046; padding:4px 0; }
QPushButton#danger { background:#5A1A16; color:#FFE3E0; border:1px solid #D9534A; font-weight:750; }
QPushButton#danger:hover { background:#7A231D; border-color:#FF7770; }
QPushButton#danger:disabled { background:#1A1110; color:#6E5654; border-color:#3A2422; }
QPushButton#primary:disabled { background:#1C2E18; color:#5E7A55; }
QLabel#badge[nivel="aviso"] { background:#33270C; color:#FFCF66; border-color:#8A6A1F; }
QLabel#badge[nivel="erro"] { background:#3A1412; color:#FF9C95; border-color:#A83C35; }
QLabel#stateChip { border-radius:10px; padding:5px 11px; font-size:12px; font-weight:800; letter-spacing:1px; background:#13241A; color:#A0B5A5; border:1px solid #2A4A35; }
QLabel#stateChip[nivel="info"] { background:#123522; color:#B5FF5B; border-color:#28633C; }
QLabel#stateChip[nivel="ok"] { background:#91EA32; color:#10200D; border-color:#91EA32; }
QLabel#stateChip[nivel="aviso"] { background:#33270C; color:#FFCF66; border-color:#8A6A1F; }
QLabel#stateChip[nivel="erro"] { background:#D9534A; color:#FFFFFF; border-color:#D9534A; }
QPlainTextEdit#eventLog { background:#07170F; color:#CFE0D2; border:1px solid #244B33; border-radius:10px; padding:8px; font-family:Consolas; font-size:12px; }
QLineEdit:disabled { color:#7E9585; border-color:#1B3524; }
QDoubleSpinBox { background:#07170F; color:#EDF5ED; border:1px solid #31553A; border-radius:8px; padding:7px 8px; min-width:110px; selection-background-color:#4C8C2E; }
QDoubleSpinBox:disabled, QComboBox:disabled, QCheckBox:disabled { color:#7E9585; border-color:#1B3524; }
QCheckBox { spacing:8px; }
QCheckBox::indicator { width:18px; height:18px; border:1px solid #47763B; border-radius:5px; background:#07170F; }
QCheckBox::indicator:checked { background:#91EA32; border-color:#91EA32; }
QPushButton#selected { background:#28562B; color:#C0FF67; border:1px solid #5E9E36; }
QLineEdit, QComboBox { background:#07170F; color:#EDF5ED; border:1px solid #31553A; border-radius:8px; padding:9px 10px; selection-background-color:#4C8C2E; }
QComboBox QAbstractItemView { background:#0A2117; color:#EDF5ED; selection-background-color:#28562B; border:1px solid #31553A; }
"""


def nome_exibido(robo):
    """Nome mostrado na tela. A chave interna "UR5e" é o follower, que é um UR5 (CB3)."""
    return {"UR5e": "UR5"}.get(robo, robo)


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def card():
    widget = QFrame()
    widget.setObjectName("card")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(13)
    return widget, layout


class AegisApp(QWidget):
    # Sinais públicos para integração futura com o controlador do Joshua.
    iniciar_solicitado = Signal()
    pausar_retomar_solicitado = Signal()
    home_solicitado = Signal()
    parar_solicitado = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AEGIS | Desarme robótico")
        self.resize(1180, 740)
        self.setMinimumSize(690, 480)
        self.setStyleSheet(STYLE)

        # Posição inicial visual da garra no modelo 3D; ainda não é gPO real.
        self.gripper_position = 255
        self.positions = {
            "UR3e": [180.0, -120.0, 250.0, 0.0, 3.142, 0.0],
            "UR5e": [350.0, -180.0, 400.0, 0.0, 3.142, 0.0],
        }
        self.joint_angles = {
            "UR3e": [0.0, -90.0, 0.0, -90.0, 0.0, 0.0],
            "UR5e": [0.0, -90.0, 0.0, -90.0, 0.0, 0.0],
        }
        self.wrenches = {
            "UR3e": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "UR5e": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
        # Parâmetros salvos neste computador (tela Configurações).
        self.config = aegis_config.carregar()
        # Leitor RTDE; conectado pelo botão Iniciar.
        self.telemetry_source = None
        self.values = {}
        self.monitor_values = {}
        self.status_labels = []
        self.source_labels = []
        self.robot_views = {}
        self.focus_robot_views = {}
        self.robot_panels = {}
        self.log_entries = []
        self.camera_focus_active = False
        self.build()
        self.focus_overlay = CameraFocusOverlay(self)
        self.focus_overlay.exitRequested.connect(self.exit_camera_focus)
        self.focus_overlay.hide()
        self.refresh_values()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)

    def build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(222)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 16)
        sidebar_layout.setSpacing(5)

        logo = QLabel()
        logo_path = Path(__file__).parent / "assets" / "aegis_logo.png"
        logo_image = QPixmap(str(logo_path))
        if not logo_image.isNull():
            # Enquadra o símbolo e o nome, preservando o PNG transparente.
            logo_image = logo_image.copy(QRect(465, 65, 750, 780))
            logo.setPixmap(logo_image.scaled(
                166, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        logo.setAlignment(Qt.AlignCenter)
        logo.setMinimumHeight(150)
        sidebar_layout.addWidget(logo)
        brand_subtitle = label("DESARME ROBÓTICO", "sideMuted")
        brand_subtitle.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(brand_subtitle)
        sidebar_layout.addSpacing(16)

        self.nav = []
        pages = [
            ("INÍCIO", ["Início"]),
            ("ESPAÇO DE TRABALHO", ["Dashboard", "Operação"]),
            ("SISTEMA", ["Configurações"]),
        ]
        index = 0
        for section, names in pages:
            sidebar_layout.addWidget(label(section, "sideSection"))
            for name in names:
                button = QPushButton(name)
                button.setObjectName("nav")
                button.setCheckable(True)
                button.clicked.connect(lambda checked=False, page=index: self.show_page(page))
                sidebar_layout.addWidget(button)
                self.nav.append(button)
                index += 1

        sidebar_layout.addStretch()
        root.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.make_home()
        self.make_dashboard()
        self.make_operation()
        self.make_settings()
        self.show_page(0)

    def page(self, title, subtitle):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.addWidget(label(title, "pageTitle"))
        header_text.addWidget(label(subtitle, "muted"))
        header.addLayout(header_text, 1)
        layout.addLayout(header)

        scroll.setWidget(body)
        self.pages.addWidget(scroll)
        return layout

    def make_home(self):
        layout = self.page("Menu inicial", "Plataforma de inspeção robótica remota")

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 24, 24)
        hero_layout.setSpacing(18)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(8)
        hero_text.addWidget(label("AEGIS  /  DEFESA ROBÓTICA", "heroEyebrow"))
        hero_text.addWidget(label("Inspeção remota em cenários de risco", "heroTitle"))
        hero_text.addWidget(label(
            "Acompanhe a plataforma Leader-Follower e visualize dados, câmeras e modelos em um só lugar.",
            "heroCopy",
        ))
        hero_layout.addLayout(hero_text, 1)
        hero_button = QPushButton("Abrir operação  →")
        hero_button.setObjectName("heroButton")
        hero_button.clicked.connect(lambda: self.show_page(2))
        hero_layout.addWidget(hero_button, alignment=Qt.AlignBottom)
        layout.addWidget(hero)

        menu_heading = QHBoxLayout()
        menu_heading.addWidget(label("Acesse a central AEGIS", "robotName"), 1)
        menu_heading.addWidget(label("ESCOLHA UMA ÁREA", "heroEyebrow"))
        layout.addLayout(menu_heading)

        tiles = QGridLayout()
        tiles.setHorizontalSpacing(14)
        tiles.setVerticalSpacing(14)
        menu_items = [
            ("01", "Visão geral", "Veja o estado do sistema e dos robôs.", 1),
            ("02", "Operação", "Controle os robôs e acompanhe telemetria, 3D e câmeras.", 2),
            ("03", "Configurações", "Consulte as informações do sistema.", 3),
        ]
        for index, (number, title, description, page_index) in enumerate(menu_items):
            tile = QFrame()
            tile.setObjectName("homeTile")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(18, 17, 18, 16)
            tile_layout.setSpacing(8)
            tile_layout.addWidget(label(number, "badge"), alignment=Qt.AlignLeft)
            tile_layout.addWidget(label(title, "sectionTitle"))
            tile_layout.addWidget(label(description, "muted"))
            open_button = QPushButton("Abrir área  →")
            open_button.setObjectName("tileButton")
            open_button.clicked.connect(lambda checked=False, target=page_index: self.show_page(target))
            tile_layout.addWidget(open_button)
            tiles.addWidget(tile, index // 2, index % 2)
        layout.addLayout(tiles)

        footer = QHBoxLayout()
        footer.addWidget(label("AEGIS  ·  UR3e Leader  →  UR5 Follower", "muted"), 1)
        layout.addLayout(footer)
        layout.addStretch()

    def robot_card(self, name, role):
        widget, layout = card()
        layout.addWidget(label(nome_exibido(name), "robotName"))
        layout.addWidget(label(role, "muted"))
        motion = label("Operação: desconectado")
        layout.addWidget(motion)
        self.status_labels.append(motion)
        layout.addSpacing(8)
        layout.addWidget(label("TCP", "muted"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        for row, axis in enumerate(["X", "Y", "Z", "Rx", "Ry", "Rz"]):
            value_label = label("0.0" if row < 3 else "0.000")
            value_label.setStyleSheet("font-family:Consolas; font-weight:700; font-size:15px;")
            self.values[(name, row)] = value_label
            grid.addWidget(label(axis), row, 0)
            grid.addWidget(value_label, row, 1)
            grid.addWidget(label("mm" if row < 3 else "rad", "muted"), row, 2)
        layout.addLayout(grid)
        layout.addStretch()
        return widget

    def make_dashboard(self):
        layout = self.page("Dashboard", "Acompanhe o estado do sistema e dos robôs em tempo real.")

        # Painel de estado mais visível, com acesso direto à tela de operação.
        status_card, status_layout = card()
        status_header = QHBoxLayout()
        status_header.addWidget(label("Status do sistema", "robotName"), 1)
        status_layout.addLayout(status_header)

        status_row = QHBoxLayout()
        status_text = QVBoxLayout()
        self.summary = label("Operação parada", "statusValue")
        self.summary.setObjectName("statusValue")
        status_text.addWidget(self.summary)
        status_text.addWidget(label("UR3e Leader  →  UR5 Follower", "muted"))
        status_row.addLayout(status_text, 1)

        operation_button = QPushButton("Abrir Operação")
        operation_button.clicked.connect(lambda: self.show_page(2))
        status_row.addWidget(operation_button)
        status_layout.addLayout(status_row)
        layout.addWidget(status_card)

        self.robot_row = QHBoxLayout()
        self.robot_row.setSpacing(16)
        self.robot_row.addWidget(self.robot_card("UR3e", "Leader • robô de controle"), 1)
        self.robot_row.addWidget(self.robot_card("UR5e", "Follower • robô manipulador"), 1)
        layout.addLayout(self.robot_row)
        layout.addStretch()

    def make_operation(self):
        layout = self.page(
            "Operação",
            "Controle da missão, telemetria, modelos 3D e câmeras",
        )
        widget, box = card()
        header = QHBoxLayout()
        header.addWidget(label("Controle da operação", "robotName"), 1)
        self.state_chip = QLabel()
        self.state_chip.setObjectName("stateChip")
        header.addWidget(self.state_chip, 0, Qt.AlignVCenter)
        box.addLayout(header)

        self.operation_controls = QHBoxLayout()
        self.operation_controls.setSpacing(10)
        self.botao_iniciar = QPushButton("Iniciar")
        self.botao_iniciar.setObjectName("primary")
        self.botao_iniciar.clicked.connect(self._solicitar_inicio)
        self.operation_controls.addWidget(self.botao_iniciar, 1)

        self.botao_home = QPushButton("Home")
        self.botao_home.clicked.connect(self._confirmar_home)
        self.operation_controls.addWidget(self.botao_home, 1)

        self.botao_pausar_retomar = QPushButton("Pausar  (P)")
        self.botao_pausar_retomar.clicked.connect(self._solicitar_pausa_retomada)
        self.operation_controls.addWidget(self.botao_pausar_retomar, 1)

        self.botao_parar = QPushButton("Parar  (Espaço)")
        self.botao_parar.setObjectName("danger")
        self.botao_parar.clicked.connect(self._solicitar_parada)
        self.operation_controls.addWidget(self.botao_parar, 1)
        for botao in (self.botao_iniciar, self.botao_home, self.botao_pausar_retomar, self.botao_parar):
            # Sem foco: Espaço nunca "clica" o botão focado em vez de parar.
            botao.setFocusPolicy(Qt.NoFocus)
        box.addLayout(self.operation_controls)
        box.addWidget(label(
            "Os botões ainda não enviam comandos aos robôs físicos. Home pede confirmação antes de solicitar a ação.",
            "muted",
        ))

        self.operation_info = label("Operação parada.", "badge")
        self.operation_info.setProperty("nivel", "info")
        box.addWidget(self.operation_info)

        indicators = QGridLayout()
        indicators.setHorizontalSpacing(8)
        indicators.setVerticalSpacing(8)
        self.indicator_values = {}
        for col, (key, caption) in enumerate((
            ("leader", "Leader"),
            ("f_follower", "Força no follower"),
            ("reflexao", "Reflexão de força"),
            ("garra", "Garra"),
        )):
            tile = QFrame()
            tile.setObjectName("metricTile")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(10, 8, 10, 8)
            tile_layout.setSpacing(3)
            tile_layout.addWidget(label(caption, "metricCaption"))
            value = label("—", "metricValue")
            tile_layout.addWidget(value)
            self.indicator_values[key] = value
            indicators.addWidget(tile, col // 4, col % 4)
        box.addLayout(indicators)
        layout.addWidget(widget)

        # Monitoramento (telemetria, modelos 3D e câmeras) fica na mesma tela.
        self.build_monitoring(layout)

        log_widget, log_box = card()
        log_box.addWidget(label("Registro de eventos", "sectionTitle"))
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("eventLog")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(300)
        self.log_view.setMinimumHeight(150)
        self.log_view.setFocusPolicy(Qt.NoFocus)
        log_box.addWidget(self.log_view)
        layout.addWidget(log_widget)

        # Atalhos de segurança valem em qualquer tela, inclusive na câmera em foco.
        atalho_parar = QShortcut(QKeySequence(Qt.Key_Space), self)
        atalho_parar.setContext(Qt.ApplicationShortcut)
        atalho_parar.activated.connect(self._atalho_parar)
        atalho_pausa = QShortcut(QKeySequence(Qt.Key_P), self)
        atalho_pausa.setContext(Qt.ApplicationShortcut)
        atalho_pausa.activated.connect(self._atalho_pausa)

        self.operation_state = None
        self.apply_operation_state("desconectado")

    # --- Estado da operação --------------------------------------------------
    STATE_TEXT = {
        "desconectado": ("Desconectado", "neutro"),
        "conectando": ("Conectando", "aviso"),
        "conectado": ("Conectado", "info"),
        "home": ("Indo para Home", "aviso"),
        "acompanhando": ("Acompanhando", "ok"),
        "pausado": ("Pausado", "aviso"),
        "parando": ("Parando", "aviso"),
        "erro": ("Erro", "erro"),
    }

    def apply_operation_state(self, state):
        """Habilita só os botões que fazem sentido no estado atual."""
        self.operation_state = state
        texto, nivel = self.STATE_TEXT.get(state, (state, "neutro"))
        self.state_chip.setText(texto.upper())
        self._set_level(self.state_chip, nivel)

        desligado = state in ("desconectado", "erro")
        self.botao_iniciar.setEnabled(desligado)
        self.botao_home.setEnabled(state in ("conectado", "acompanhando", "pausado"))
        self.botao_pausar_retomar.setEnabled(state in ("acompanhando", "pausado"))
        self.botao_pausar_retomar.setText("Retomar  (P)" if state == "pausado" else "Pausar  (P)")
        self.botao_parar.setEnabled(not desligado and state != "parando")
        # IPs só podem mudar com os robôs desconectados.
        self.ur3e_ip.setEnabled(desligado)
        self.ur5e_ip.setEnabled(desligado)
        # Parâmetros também só mudam com os robôs desconectados.
        for nome in ("settings_panel", "botao_salvar_config", "botao_padroes_config"):
            widget = getattr(self, nome, None)
            if widget is not None:
                widget.setEnabled(desligado)
        if hasattr(self, "settings_status"):
            self.settings_status.setText(
                "" if desligado else "Pressione Parar para alterar os parâmetros."
            )
        if desligado:
            self.set_indicators({})  # sem controle ativo, nada a indicar
        self.summary.setText(texto)
        for item in self.status_labels:
            item.setText(f"Operação: {texto.lower()}")

    def set_message(self, text, nivel="info"):
        self.operation_info.setText(text)
        self._set_level(self.operation_info, nivel)

    def set_indicators(self, info):
        f = info.get("f_follower")
        valores = {
            "leader": info.get("leader", "—"),
            "f_follower": "—" if f is None else f"{f:.0f} N",
            "reflexao": info.get("reflexao", "—"),
            "garra": info.get("garra", "—"),
        }
        for key, value in valores.items():
            self.indicator_values[key].setText(str(value).capitalize() if key != "f_follower" else value)

    @staticmethod
    def _set_level(widget, nivel):
        widget.setProperty("nivel", nivel)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _atalho_parar(self):
        if self.botao_parar.isEnabled():
            self._solicitar_parada()

    def _atalho_pausa(self):
        if self.botao_pausar_retomar.isEnabled():
            self._solicitar_pausa_retomada()

    def build_monitoring(self, layout):
        """Monta telemetria, modelos 3D e câmeras dentro do layout da Operação."""
        self.monitor_tabs = QTabWidget()
        readings_tab = QWidget()
        readings_layout = QVBoxLayout(readings_tab)
        readings_layout.setContentsMargins(4, 12, 4, 4)
        readings_layout.setSpacing(14)

        connection_card, connection_layout = card()
        connection_layout.addWidget(label("Fonte das leituras", "sectionTitle"))
        connection_layout.addWidget(label(
            "As medidas aparecem ao pressionar Iniciar. Os IPs só podem ser alterados com os robôs desconectados.",
            "muted",
        ))
        address_row = QHBoxLayout()
        self.ur3e_ip = QLineEdit(self.config["ip_leader"])
        self.ur3e_ip.setPlaceholderText("IP do UR3e Leader")
        self.ur5e_ip = QLineEdit(self.config["ip_follower"])
        self.ur5e_ip.setPlaceholderText("IP do UR5 Follower")
        address_row.addWidget(label("UR3e Leader"))
        address_row.addWidget(self.ur3e_ip, 1)
        address_row.addWidget(label("UR5 Follower"))
        address_row.addWidget(self.ur5e_ip, 1)
        connection_layout.addLayout(address_row)

        action_row = QHBoxLayout()
        self.telemetry_status = label("Desconectado • pressione Iniciar", "badge")
        action_row.addWidget(self.telemetry_status, 1)
        connection_layout.addLayout(action_row)
        readings_layout.addWidget(connection_card)

        self.monitor_row = QHBoxLayout()
        self.monitor_row.setSpacing(16)
        self.monitor_row.addWidget(self.monitor_robot_card("UR3e", "LEADER"), 1)
        self.monitor_row.addWidget(self.monitor_robot_card("UR5e", "FOLLOWER"), 1)
        readings_layout.addLayout(self.monitor_row)
        readings_layout.addWidget(label(
            "As leituras vêm dos robôs via RTDE, somente leitura.",
            "muted",
        ))
        readings_layout.addStretch()

        visual_tab = QWidget()
        visual_layout = QVBoxLayout(visual_tab)
        visual_layout.setContentsMargins(4, 12, 4, 4)
        visual_layout.setSpacing(10)
        visual_layout.addWidget(label(
            "Modelos 3D manipuláveis • arraste para girar • roda do mouse para aproximar • arraste a divisória para redimensionar",
            "muted",
        ))

        self.expanded_camera = None
        self.view_splitter = QSplitter(Qt.Vertical)
        self.view_splitter.setChildrenCollapsible(False)
        self.visualization_card, visualization_layout = card()
        visualization_layout.addWidget(label("Modelos UR3e e UR5", "sectionTitle"))
        self.visual_row = QHBoxLayout()
        self.visual_row.setSpacing(14)
        for robot_name, role in (("UR3e", "LEADER"), ("UR5e", "FOLLOWER")):
            panel = QFrame()
            panel.setObjectName("softPanel")
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(10, 9, 10, 8)
            panel_layout.setSpacing(4)
            panel_layout.addWidget(label(f"{nome_exibido(robot_name)}  ·  {role}", "sectionTitle"))
            view = RobotArmView(robot_name)
            self.robot_views[robot_name] = view
            self.robot_panels[robot_name] = panel
            panel_layout.addWidget(view, 1)
            self.visual_row.addWidget(panel, 1)
        visualization_layout.addLayout(self.visual_row)
        self.view_splitter.addWidget(self.visualization_card)

        self.cameras_card, cameras_layout = card()
        cameras_layout.addWidget(label("Câmeras USB", "sectionTitle"))
        self.camera_row = QHBoxLayout()
        self.camera_row.setSpacing(12)
        self.camera_panels = []
        for title in ("Webcam", "Câmera da garra"):
            camera_panel = CameraPanel(title)
            camera_panel.expandRequested.connect(self.toggle_camera_expansion)
            self.camera_panels.append(camera_panel)
            self.camera_row.addWidget(camera_panel, 1)
        cameras_layout.addLayout(self.camera_row)
        self.view_splitter.addWidget(self.cameras_card)
        self.view_splitter.setStretchFactor(0, 3)
        self.view_splitter.setStretchFactor(1, 2)
        visual_layout.addWidget(self.view_splitter, 1)

        self.monitor_tabs.addTab(readings_tab, "Telemetria")
        self.monitor_tabs.addTab(visual_tab, "Câmeras e visualização 3D")
        layout.addWidget(self.monitor_tabs, 1)
        layout.addStretch()
        self.refresh_monitor()
        self.refresh_robot_views()

    def toggle_camera_expansion(self, selected_panel):
        """Abre a câmera em tela cheia ou alterna qual câmera fica principal."""
        if self.camera_focus_active:
            if self.expanded_camera is selected_panel:
                self.exit_camera_focus()
            else:
                self.switch_focus_camera(selected_panel)
            return

        self.enter_camera_focus(selected_panel)

    def enter_camera_focus(self, selected_panel):
        self._restore_was_fullscreen = self.isFullScreen()
        self._restore_was_maximized = self.isMaximized()
        self.camera_focus_active = True
        self.expanded_camera = selected_panel
        other_panel = next(panel for panel in self.camera_panels if panel is not selected_panel)

        self.camera_row.removeWidget(selected_panel)
        self.camera_row.removeWidget(other_panel)
        selected_panel.setParent(None)
        other_panel.setParent(None)
        selected_panel.set_focus_mode("main")
        other_panel.set_focus_mode("pip")
        self.focus_overlay.set_main_widget(selected_panel)
        self.focus_overlay.set_camera_pip(other_panel)
        self.focus_overlay.set_camera_title(
            selected_panel.title_label.text(), other_panel.title_label.text()
        )

        robot_tabs = QTabWidget()
        self.focus_overlay.set_robot_pip(robot_tabs)
        self.focus_robot_views.clear()
        for robot_name in ("UR3e", "UR5e"):
            panel = QWidget(robot_tabs)
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(2, 2, 2, 2)
            mini_view = RobotArmView(robot_name, parent=panel, compact=True)
            self.focus_robot_views[robot_name] = mini_view
            panel_layout.addWidget(mini_view)
            robot_tabs.addTab(panel, nome_exibido(robot_name))
        self._focus_robot_tabs = robot_tabs

        self.showFullScreen()
        self.sidebar.hide()
        self.pages.hide()
        self.focus_overlay.setGeometry(self.rect())
        self.focus_overlay.show()
        self.focus_overlay.raise_()

    def switch_focus_camera(self, selected_panel):
        current_main = self.focus_overlay.take_main_widget()
        pip_camera = self.focus_overlay.take_camera_pip()
        if selected_panel is not pip_camera:
            selected_panel = pip_camera
        current_main.set_focus_mode("pip")
        selected_panel.set_focus_mode("main")
        self.focus_overlay.set_main_widget(selected_panel)
        self.focus_overlay.set_camera_pip(current_main)
        self.expanded_camera = selected_panel
        self.focus_overlay.set_camera_title(
            selected_panel.title_label.text(), current_main.title_label.text()
        )

    def exit_camera_focus(self):
        if not self.camera_focus_active:
            return
        self.focus_overlay.hide_pips()
        main_panel = self.focus_overlay.take_main_widget()
        pip_camera = self.focus_overlay.take_camera_pip()
        robot_tabs = self.focus_overlay.take_robot_pip()
        if main_panel is not None:
            main_panel.restore_normal_mode()
            self.camera_row.addWidget(main_panel, 1)
        if pip_camera is not None:
            pip_camera.restore_normal_mode()
            self.camera_row.addWidget(pip_camera, 1)
        if robot_tabs is not None:
            self.focus_robot_views.clear()
            robot_tabs.deleteLater()

        self.focus_overlay.hide()
        self.camera_focus_active = False
        self.expanded_camera = None
        self.sidebar.show()
        self.pages.show()
        self.monitor_tabs.setCurrentIndex(1)
        if self._restore_was_fullscreen:
            self.showFullScreen()
        elif self._restore_was_maximized:
            self.showMaximized()
        else:
            self.showNormal()
        self.view_splitter.setSizes([3, 2])
        QTimer.singleShot(0, self.refresh_robot_views)


    def metric_tile(self, title, value, key):
        tile = QFrame()
        tile.setObjectName("metricTile")
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(10, 8, 10, 8)
        tile_layout.setSpacing(3)
        tile_layout.addWidget(label(title, "metricCaption"))
        value_label = label(value, "metricValue")
        tile_layout.addWidget(value_label)
        self.monitor_values[key] = value_label
        return tile

    def monitor_section(self, title, metrics):
        panel = QFrame()
        panel.setObjectName("softPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 11, 12, 12)
        panel_layout.setSpacing(9)
        panel_layout.addWidget(label(title, "sectionTitle"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for index, (caption, initial, key) in enumerate(metrics):
            grid.addWidget(self.metric_tile(caption, initial, key), index // 3, index % 3)
        panel_layout.addLayout(grid)
        return panel

    def monitor_robot_card(self, name, role):
        widget, layout = card()
        header = QHBoxLayout()
        header.addWidget(label(nome_exibido(name), "robotName"), 1)
        header.addWidget(label(role, "roleBadge"))
        layout.addLayout(header)
        source_label = label("Sem leitura • pressione Iniciar", "muted")
        self.source_labels.append(source_label)
        layout.addWidget(source_label)

        joint_metrics = [
            (f"Junta {i + 1}", "0,0°", (name, "joint", i)) for i in range(6)
        ]
        tcp_axes = ["X", "Y", "Z", "Rx", "Ry", "Rz"]
        tcp_metrics = [
            (axis, "0.0 mm" if i < 3 else "0.000 rad", (name, "tcp", i))
            for i, axis in enumerate(tcp_axes)
        ]
        wrench_metrics = [
            (axis, "0.00 N" if i < 3 else "0.000 Nm", (name, "wrench", i))
            for i, axis in enumerate(["Fx", "Fy", "Fz", "Tx", "Ty", "Tz"])
        ]

        layout.addWidget(self.monitor_section("Ângulos das juntas", joint_metrics))
        layout.addWidget(self.monitor_section("TCP em relação à base", tcp_metrics))
        layout.addWidget(self.monitor_section("Força e torque no TCP", wrench_metrics))
        return widget

    def make_settings(self):
        layout = self.page(
            "Configurações",
            "Parâmetros do controle. Valem a partir do próximo Iniciar e ficam salvos neste computador.",
        )
        self.settings_widgets = {}
        self.settings_panel = QWidget()
        panel_layout = QVBoxLayout(self.settings_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(18)

        def numero(chave, sufixo, casas, passo, ajuda):
            lo, hi = aegis_config.LIMITES[chave]
            campo = QDoubleSpinBox()
            campo.setRange(lo, hi)
            campo.setDecimals(casas)
            campo.setSingleStep(passo)
            if sufixo:
                campo.setSuffix(f" {sufixo}")
            campo.setToolTip(ajuda)
            self.settings_widgets[chave] = campo
            return campo

        def secao(titulo, descricao, linhas):
            widget, box = card()
            box.addWidget(label(titulo, "robotName"))
            box.addWidget(label(descricao, "muted"))
            form = QFormLayout()
            form.setHorizontalSpacing(18)
            form.setVerticalSpacing(10)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            for texto, campo, ajuda in linhas:
                linha = QHBoxLayout()
                linha.setSpacing(16)
                # Largura fixa: campos alinhados em todas as seções.
                campo.setFixedWidth(260 if isinstance(campo, QComboBox) else 150)
                linha.addWidget(campo)
                linha.addWidget(label(ajuda, "muted"), 1)
                nome = QLabel(texto)
                nome.setFixedWidth(130)
                form.addRow(nome, linha)
            box.addLayout(form)
            panel_layout.addWidget(widget)

        self.porta_garra = QComboBox()
        self.porta_garra.addItem("Automática (câmera do punho)", "auto")
        for porta in aegis_config.portas_seriais():
            self.porta_garra.addItem(porta, porta)
        self.settings_widgets["porta_garra"] = self.porta_garra
        secao("Garra", "Porta serial da garra Robotiq (passa pela câmera do punho).", [
            ("Porta", self.porta_garra, "Use Automática, a menos que a garra não seja encontrada."),
        ])

        secao("Leader", "Como o UR3e responde à mão do operador.", [
            ("Amortecimento", numero("amortecimento", "", 3, 0.005, ""),
             "Maior: para mais rápido ao soltar. Menor: desliza mais."),
            ("Ganho de força", numero("ganho_forca", "", 2, 0.1, ""),
             "Maior: responde mais rápido ao empurrão (acima de 1 pode oscilar)."),
            ("Força para guiar", numero("f_entra_force", "N", 1, 0.1, ""),
             "Acima disso o leader sai do teach mode e passa a seguir a mão."),
        ])

        self.reflexao_ativa = QCheckBox("Ativada")
        self.settings_widgets["reflexao"] = self.reflexao_ativa
        secao("Reflexão de força", "Contato no follower (UR5) sentido na mão, no leader.", [
            ("Reflexão", self.reflexao_ativa, ""),
            ("Ganho", numero("k_reflexao", "", 2, 0.01, ""),
             "N aplicados no leader para cada N estimado no follower."),
            ("Zona morta", numero("zona_morta_reflexao", "N", 0, 5, ""),
             "Forças menores são ruído da estimativa do UR5 e são ignoradas."),
            ("Força máxima", numero("fmax_reflexao", "N", 1, 0.5, ""),
             "Limite da força aplicada no leader."),
        ])
        layout.addWidget(self.settings_panel)

        actions = QHBoxLayout()
        self.botao_salvar_config = QPushButton("Salvar")
        self.botao_salvar_config.setObjectName("primary")
        self.botao_salvar_config.clicked.connect(self.salvar_configuracoes)
        self.botao_padroes_config = QPushButton("Restaurar padrões")
        self.botao_padroes_config.clicked.connect(self.restaurar_configuracoes)
        actions.addWidget(self.botao_salvar_config)
        actions.addWidget(self.botao_padroes_config)
        self.settings_status = label("", "muted")
        actions.addWidget(self.settings_status, 1)
        layout.addLayout(actions)
        layout.addStretch()
        self._mostrar_configuracoes(self.config)

    def _mostrar_configuracoes(self, cfg):
        for chave, campo in self.settings_widgets.items():
            valor = cfg[chave]
            if isinstance(campo, QDoubleSpinBox):
                campo.setValue(valor)
            elif isinstance(campo, QCheckBox):
                campo.setChecked(bool(valor))
            elif isinstance(campo, QComboBox):
                indice = campo.findData(valor)
                if indice < 0:  # porta salva que não está conectada agora
                    campo.addItem(f"{valor} (não encontrada)", valor)
                    indice = campo.count() - 1
                campo.setCurrentIndex(indice)

    def _ler_configuracoes(self):
        cfg = dict(self.config)
        for chave, campo in self.settings_widgets.items():
            if isinstance(campo, QDoubleSpinBox):
                cfg[chave] = campo.value()
            elif isinstance(campo, QCheckBox):
                cfg[chave] = campo.isChecked()
            elif isinstance(campo, QComboBox):
                cfg[chave] = campo.currentData()
        cfg["ip_leader"] = self.ur3e_ip.text().strip()
        cfg["ip_follower"] = self.ur5e_ip.text().strip()
        return cfg

    def salvar_configuracoes(self):
        try:
            self.config = aegis_config.salvar(self._ler_configuracoes())
        except OSError as error:
            self.settings_status.setText(f"Não foi possível salvar: {error}")
            return
        self._mostrar_configuracoes(self.config)
        self.settings_status.setText(f"Salvo às {time.strftime('%H:%M:%S')}. Vale a partir do próximo Iniciar.")
        self.add_log("Configurações salvas.")

    def restaurar_configuracoes(self):
        padroes = dict(aegis_config.PADROES)
        padroes["ip_leader"] = self.ur3e_ip.text().strip()
        padroes["ip_follower"] = self.ur5e_ip.text().strip()
        self._mostrar_configuracoes(padroes)
        self.settings_status.setText("Valores padrão carregados. Pressione Salvar para manter.")

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        for page_index, button in enumerate(self.nav):
            button.setChecked(page_index == index)

    def _solicitar_inicio(self):
        """Emite o evento de interface e conecta a telemetria."""
        self.iniciar_solicitado.emit()
        self.connect_telemetry()

    def _solicitar_pausa_retomada(self):
        self.pausar_retomar_solicitado.emit()

    def _solicitar_parada(self):
        self.parar_solicitado.emit()

    def _confirmar_home(self):
        resposta = QMessageBox.question(
            self,
            "Confirmar Home",
            "Deseja solicitar o retorno à posição Home?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            self.home_solicitado.emit()

    def add_log(self, text, nivel="info"):
        self.log_entries.append(text)
        self.log_entries = self.log_entries[-100:]
        log_view = getattr(self, "log_view", None)
        if log_view is not None:
            marca = {"aviso": "AVISO  ", "erro": "ERRO   "}.get(nivel, "")
            log_view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {marca}{text}")

    def tick(self):
        if self.telemetry_source is not None:
            try:
                self.update_from_telemetry()
            except Exception as error:
                self.disconnect_telemetry(
                    f"Falha na leitura RTDE: {str(error)[:70]}"
                )
        self.refresh_values()
        self.refresh_monitor()
        self.refresh_robot_views()

    def connect_telemetry(self):
        """Conecta aos dois robôs apenas para receber dados, sem comandos."""
        if self.telemetry_source is not None:
            return
        addresses = {
            "UR3e": self.ur3e_ip.text().strip(),
            "UR5e": self.ur5e_ip.text().strip(),
        }
        if not all(addresses.values()):
            self.telemetry_status.setText("Informe os dois endereços IP")
            return

        self.telemetry_status.setText("Conectando para leitura...")
        QApplication.processEvents()
        source = None
        try:
            # Import tardio: a biblioteca RTDE só é carregada após o clique.
            try:
                from .rtde_telemetry import RTDETelemetrySource
            except ImportError:
                from rtde_telemetry import RTDETelemetrySource
            source = RTDETelemetrySource(addresses)
            source.connect()
            source.read()  # valida a leitura inicial antes de mudar o estado da UI
            self.set_telemetry_source(source)
            self.telemetry_status.setText("Conectado • telemetria real, somente leitura")
            self._set_level(self.telemetry_status, "info")
            for source_label in self.source_labels:
                source_label.setText("RTDE • leitura real, somente leitura")
            for status_label in self.status_labels:
                status_label.setText("Telemetria conectada")
            self.add_log("Telemetria RTDE conectada (somente leitura)")
        except Exception as error:
            if source is not None:
                source.close()
            self.telemetry_status.setText(f"Não conectou: {str(error)[:75]}")
            self._set_level(self.telemetry_status, "erro")
            self.add_log("Falha ao conectar telemetria RTDE")

    def disconnect_telemetry(self, status="Desconectado • pressione Iniciar"):
        """Fecha a leitura (usado quando a leitura RTDE falha)."""
        source, self.telemetry_source = self.telemetry_source, None
        self.telemetry_status.setText(status)
        self._set_level(self.telemetry_status, "info")
        for source_label in self.source_labels:
            source_label.setText("Sem leitura • pressione Iniciar")
        if source is not None:
            source.close()
            self.add_log("Telemetria RTDE desconectada")

    def update_from_telemetry(self):
        """Atualiza a interface com uma fonte RTDE somente de leitura."""
        samples = self.telemetry_source.read()
        for name in ("UR3e", "UR5e"):
            sample = samples[name]
            self.joint_angles[name] = [math.degrees(value) for value in sample.joint_positions_rad]
            pose = sample.tcp_pose_m_rad
            self.positions[name] = [pose[0] * 1000, pose[1] * 1000, pose[2] * 1000, *pose[3:]]
            self.wrenches[name] = list(sample.tcp_wrench_n_nm)

    def set_telemetry_source(self, source):
        """Injeta um leitor já conectado. Não conecta automaticamente ao robô."""
        self.telemetry_source = source

    def closeEvent(self, event):
        if self.telemetry_source is not None:
            self.telemetry_source.close()
        for camera_panel in getattr(self, "camera_panels", []):
            camera_panel.stop_camera()
        super().closeEvent(event)

    def refresh_values(self):
        real = self.telemetry_source is not None
        for name, position in self.positions.items():
            for index, value in enumerate(position):
                if not real:
                    formatted = "—"  # sem leitura: nunca mostrar números de exemplo
                else:
                    formatted = f"{value:.1f}" if index < 3 else f"{value:.3f}"
                self.values[(name, index)].setText(formatted)

    def refresh_monitor(self):
        if not self.monitor_values:
            return
        if self.telemetry_source is None:
            for value_label in self.monitor_values.values():
                value_label.setText("—")
            return
        for name in self.positions:
            for index, value in enumerate(self.joint_angles[name]):
                self.monitor_values[(name, "joint", index)].setText(f"{value:.1f}°")
            for index, value in enumerate(self.positions[name]):
                if index < 3:
                    formatted = f"{value:.1f} mm"
                else:
                    formatted = f"{value:.3f} rad"
                self.monitor_values[(name, "tcp", index)].setText(formatted)
            for index, value in enumerate(self.wrenches[name]):
                formatted = f"{value:.2f} N" if index < 3 else f"{value:.3f} Nm"
                self.monitor_values[(name, "wrench", index)].setText(formatted)

    def refresh_robot_views(self):
        for name, view in self.robot_views.items():
            view.set_joint_angles(self.joint_angles[name])
        for name, view in self.focus_robot_views.items():
            view.set_joint_angles(self.joint_angles[name])
        follower_view = self.robot_views.get("UR5e")
        if follower_view is not None:
            follower_view.set_gripper_position(self.gripper_position)
        focus_follower = self.focus_robot_views.get("UR5e")
        if focus_follower is not None:
            focus_follower.set_gripper_position(self.gripper_position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.camera_focus_active:
            self.focus_overlay.setGeometry(self.rect())
            self.focus_overlay.raise_()
        if hasattr(self, "robot_row"):
            narrow = self.width() < 930
            self.sidebar.setFixedWidth(170 if narrow else 222)
            # Largura útil da página (janela menos barra lateral e margens).
            content = self.width() - self.sidebar.width() - 70

            def empilhar(row, largura_minima):
                vertical = content < largura_minima
                direcao = QVBoxLayout.TopToBottom if vertical else QHBoxLayout.LeftToRight
                if row.direction() == direcao:
                    return
                row.setDirection(direcao)
                # Recalcula o tamanho mínimo do card e de todos os pais
                # (abas, divisória, página), senão a rolagem horizontal fica.
                dono = row.parentWidget()
                while dono is not None and dono is not self:
                    if dono.layout() is not None:
                        dono.layout().invalidate()
                    dono.updateGeometry()
                    dono = dono.parentWidget()

            # Cada linha empilha quando seus itens lado a lado não cabem mais.
            empilhar(self.robot_row, 760)
            empilhar(self.monitor_row, 760)
            if hasattr(self, "visual_row"):
                empilhar(self.visual_row, 720)
            if hasattr(self, "camera_row"):
                empilhar(self.camera_row, 980)
            if hasattr(self, "operation_controls"):
                empilhar(self.operation_controls, 560)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AegisApp()
    window.show()
    sys.exit(app.exec())
