import math
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from .robot_view import RobotArmView
    from .camera_panel import CameraPanel
    from .focus_overlay import CameraFocusOverlay
except ImportError:
    from robot_view import RobotArmView
    from camera_panel import CameraPanel
    from focus_overlay import CameraFocusOverlay


# Interface demonstrativa. Este arquivo não importa nem conecta ao ur_rtde.
STYLE = """
QWidget { background:#F3F7FA; color:#18384A; font-family:'Segoe UI'; font-size:14px; }
QFrame#sidebar { background:#102C3D; border-radius:22px; }
QFrame#card { background:white; border:1px solid #E4ECF1; border-radius:18px; }
QFrame#softPanel { background:#F7FAFC; border:1px solid #E5EDF2; border-radius:13px; }
QFrame#metricTile { background:white; border:1px solid #E5EDF2; border-radius:11px; }
QFrame#heroCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #145A78,stop:1 #168575); border:0; border-radius:22px; }
QFrame#homeTile { background:white; border:1px solid #E4ECF1; border-radius:17px; }
QFrame#sideStatus { background:#18394B; border:1px solid #2B4A5B; border-radius:14px; }
QTabWidget::pane { background:white; border:1px solid #E4ECF1; border-radius:13px; top:-1px; }
QTabBar::tab { background:#EEF4F7; color:#61798B; padding:10px 17px; margin-right:5px; border-radius:9px 9px 0 0; font-weight:650; }
QTabBar::tab:selected { background:#DDF3EE; color:#126B61; }
QSplitter::handle:vertical { background:#DCE7EC; height:8px; border-radius:4px; }
QLabel { background:transparent; }
QLabel#pageTitle { font-size:29px; font-weight:700; color:#18384A; }
QLabel#brand { font-size:27px; font-weight:800; color:white; letter-spacing:1px; }
QLabel#brandMark { background:#BDEFE4; color:#126A61; border-radius:13px; font-size:23px; font-weight:800; }
QLabel#sideSection { color:#91AAB8; font-size:10px; font-weight:700; letter-spacing:1px; padding:8px 10px 2px; }
QLabel#sideMuted { color:#A9C0CC; }
QLabel#robotName { font-size:21px; font-weight:700; }
QLabel#sectionTitle { font-size:14px; font-weight:700; color:#214D6C; }
QLabel#metricCaption { color:#61798B; font-size:12px; font-weight:600; }
QLabel#metricValue { color:#173B56; font-size:15px; font-weight:700; }
QLabel#muted { color:#61798B; }
QLabel#badge { background:#E4F4F2; color:#167365; border-radius:11px; padding:7px 12px; font-weight:700; }
QLabel#roleBadge { background:#E8F5F2; color:#14705F; border-radius:10px; padding:6px 10px; font-weight:700; }
QLabel#statusValue { font-size:18px; font-weight:700; }
QLabel#heroTitle { color:white; font-size:28px; font-weight:700; }
QLabel#heroCopy { color:#E0F3F1; font-size:14px; }
QLabel#heroEyebrow { color:#BCECE2; font-size:11px; font-weight:700; letter-spacing:1px; }
QLabel#modelPlaceholder { background:#F7FAFC; color:#61798B; border:1px dashed #B8CAD3; border-radius:12px; padding:18px; }
QPushButton { background:#F2F7FA; color:#21465B; border:1px solid #DFE9EF; border-radius:11px; padding:11px 15px; font-weight:650; }
QPushButton:hover { background:#E4F1F5; }
QPushButton#nav { text-align:left; color:#C5D7E0; background:transparent; border:0; border-radius:11px; padding:12px; }
QPushButton#nav:hover { background:#1B3D50; color:white; }
QPushButton#nav:checked { background:#D9F3EE; color:#11675B; }
QPushButton#primary { background:#167F73; color:white; border:0; }
QPushButton#primary:hover { background:#126D64; }
QPushButton#demo { background:#E2F4EF; color:#11675B; border:1px solid #C9E8DE; }
QPushButton#heroButton { background:white; color:#125D63; border:0; border-radius:11px; padding:12px 17px; font-weight:700; }
QPushButton#heroButton:hover { background:#E8F8F4; }
QPushButton#tileButton { text-align:left; background:transparent; border:0; color:#147365; padding:4px 0; }
QPushButton#danger { background:#FCE9EB; color:#A51E35; border:0; }
QPushButton#selected { background:#1477AC; color:white; }
QSlider::groove:horizontal { height:7px; background:#D7E6F1; border-radius:3px; }
QSlider::handle:horizontal { background:#168A76; width:17px; margin:-6px 0; border-radius:8px; }
"""


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


class ELO(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ELO | Leader-Follower — Demonstração")
        self.resize(1180, 740)
        self.setMinimumSize(690, 480)
        self.setStyleSheet(STYLE)

        self.running = False
        self.paused = False
        self.t = 0.0
        self.speed = 50
        self.scale = 1.0
        # gPO do Robotiq: 0 = aberta, 255 = fechada. Na demo, o botão
        # abaixo controla apenas o modelo 3D e não envia comandos à garra.
        self.gripper_position = 255
        self.gripper_target = 255
        self.gripper_previous_position = 255
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
        # None mantém a aplicação estritamente no modo simulado.
        # Um adaptador RTDE só pode ser fornecido e conectado explicitamente.
        self.telemetry_source = None
        self.values = {}
        self.monitor_values = {}
        self.status_labels = []
        self.source_labels = []
        self.robot_views = {}
        self.robot_panels = {}
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

        brand_row = QHBoxLayout()
        brand_mark = label("E", "brandMark")
        brand_mark.setAlignment(Qt.AlignCenter)
        brand_mark.setFixedSize(42, 42)
        brand_row.addWidget(brand_mark)
        brand_name = QVBoxLayout()
        brand_name.addWidget(label("ELO", "brand"))
        brand_name.addWidget(label("ROBOTIC CARE", "sideMuted"))
        brand_row.addLayout(brand_name)
        brand_row.addStretch()
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(26)

        self.nav = []
        pages = [
            ("INÍCIO", ["Início"]),
            ("ESPAÇO DE TRABALHO", ["Dashboard", "Operação"]),
            ("ACOMPANHAMENTO", ["Parâmetros", "Monitoramento", "Logs"]),
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
        status_panel = QFrame()
        status_panel.setObjectName("sideStatus")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(12, 11, 12, 11)
        status_layout.setSpacing(4)
        status_layout.addWidget(label("AMBIENTE", "sideMuted"))
        status_layout.addWidget(label("●  Demonstração", "sideMuted"))
        sidebar_layout.addWidget(status_panel)
        root.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.make_home()
        self.make_dashboard()
        self.make_operation()
        self.make_parameters()
        self.make_monitoring()
        self.make_logs()
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
        header.addWidget(label("ⓘ  Modo Demonstração", "badge"), alignment=Qt.AlignTop)
        layout.addLayout(header)

        scroll.setWidget(body)
        self.pages.addWidget(scroll)
        return layout

    def make_home(self):
        layout = self.page("Menu inicial", "Escolha uma área para começar")

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 24, 24)
        hero_layout.setSpacing(18)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(8)
        hero_text.addWidget(label("TECNOLOGIA QUE CONECTA. CUIDADO QUE APROXIMA.", "heroEyebrow"))
        hero_text.addWidget(label("Bem-vinda ao ELO", "heroTitle"))
        hero_text.addWidget(label(
            "Explore a experiência Leader-Follower e acompanhe os dados da demonstração em um só lugar.",
            "heroCopy",
        ))
        hero_layout.addLayout(hero_text, 1)
        hero_button = QPushButton("Começar simulação  →")
        hero_button.setObjectName("heroButton")
        hero_button.clicked.connect(lambda: self.show_page(2))
        hero_layout.addWidget(hero_button, alignment=Qt.AlignBottom)
        layout.addWidget(hero)

        menu_heading = QHBoxLayout()
        menu_heading.addWidget(label("O que você quer fazer?", "robotName"), 1)
        menu_heading.addWidget(label("ESCOLHA UMA ÁREA", "muted"))
        layout.addLayout(menu_heading)

        tiles = QGridLayout()
        tiles.setHorizontalSpacing(14)
        tiles.setVerticalSpacing(14)
        menu_items = [
            ("01", "Visão geral", "Veja o estado do sistema e os dois robôs.", 1),
            ("02", "Operação", "Inicie, pause ou encerre a simulação.", 2),
            ("03", "Monitoramento", "Acompanhe juntas, pose, forças e torques.", 4),
            ("04", "Parâmetros", "Ajuste velocidade e escala da demonstração.", 3),
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
        footer.addWidget(label("UR3e Leader  ·  UR5e Follower", "muted"), 1)
        footer.addWidget(label("MODO DE DEMONSTRAÇÃO", "badge"))
        layout.addLayout(footer)
        layout.addStretch()

    def robot_card(self, name, role):
        widget, layout = card()
        layout.addWidget(label(name, "robotName"))
        layout.addWidget(label(role, "muted"))
        layout.addWidget(label("Estado: disponível no simulador"))
        layout.addWidget(label("Conexão física: desativada", "muted"))
        motion = label("Movimento: parado")
        layout.addWidget(motion)
        self.status_labels.append(motion)
        layout.addSpacing(8)
        layout.addWidget(label("TCP • valores simulados", "muted"))

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
        layout = self.page("ELO", "Tecnologia que conecta. Cuidado que aproxima.")

        # Painel de estado mais visível, com acesso direto à tela de operação.
        status_card, status_layout = card()
        status_header = QHBoxLayout()
        status_header.addWidget(label("Status do sistema", "robotName"), 1)
        status_header.addWidget(label("SIMULAÇÃO", "badge"))
        status_layout.addLayout(status_header)

        status_row = QHBoxLayout()
        status_text = QVBoxLayout()
        self.summary = label("Simulação pronta • operação parada", "statusValue")
        self.summary.setObjectName("statusValue")
        status_text.addWidget(self.summary)
        status_text.addWidget(label("UR3e Leader  →  UR5e Follower", "muted"))
        status_row.addLayout(status_text, 1)

        operation_button = QPushButton("Abrir Operação")
        operation_button.clicked.connect(lambda: self.show_page(2))
        status_row.addWidget(operation_button)
        status_layout.addLayout(status_row)

        self.summary_params = label("Velocidade: 50%     |     Escala: 1,0×", "muted")
        status_layout.addWidget(self.summary_params)
        layout.addWidget(status_card)

        self.robot_row = QHBoxLayout()
        self.robot_row.setSpacing(16)
        self.robot_row.addWidget(self.robot_card("UR3e", "Leader • robô de referência"), 1)
        self.robot_row.addWidget(self.robot_card("UR5e", "Follower • robô seguidor"), 1)
        layout.addLayout(self.robot_row)
        layout.addStretch()

    def make_operation(self):
        layout = self.page("Operação", "Controle simulado do sistema Leader-Follower")
        widget, box = card()
        box.addWidget(label("Controle da operação", "robotName"))
        for title, callback, object_name in [
            ("▶  Iniciar", self.start, "primary"),
            ("Ⅱ  Pausar / Retomar", self.pause, None),
            ("■  Parar", self.stop, "danger"),
            ("⌂  Home (demo)", self.move_simulated_home, None),
        ]:
            button = QPushButton(title)
            if object_name:
                button.setObjectName(object_name)
            button.clicked.connect(callback)
            box.addWidget(button)
        box.addWidget(label(
            "Home e os demais controles de Operação atuam somente na demonstração nesta versão.",
            "muted",
        ))
        layout.addWidget(widget)
        self.operation_info = label("Operação parada. Nenhum robô real é controlado.", "badge")
        layout.addWidget(self.operation_info)
        layout.addStretch()

    def make_parameters(self):
        layout = self.page("Parâmetros", "Ajustes utilizados somente na simulação")
        widget, box = card()
        box.addWidget(label("Velocidade simulada", "robotName"))
        self.speed_label = label("50%")
        box.addWidget(self.speed_label)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(5, 100)
        slider.setSingleStep(5)
        slider.setValue(50)
        slider.valueChanged.connect(self.change_speed)
        box.addWidget(slider)

        box.addWidget(label("Escala de movimento", "robotName"))
        buttons = QHBoxLayout()
        self.scale_buttons = []
        for value in [0.5, 1.0, 2.0]:
            button = QPushButton(f'{str(value).replace(".", ",")}×')
            button.clicked.connect(lambda checked=False, scale=value: self.change_scale(scale))
            buttons.addWidget(button)
            self.scale_buttons.append((value, button))
        box.addLayout(buttons)
        layout.addWidget(widget)
        layout.addWidget(label("Os valores acima não alteram os limites de segurança dos robôs físicos.", "muted"))
        layout.addStretch()
        self.change_scale(1.0)

    def make_monitoring(self):
        layout = self.page(
            "Monitoramento",
            "Leituras, modelo 3D e câmeras em uma única tela",
        )

        self.monitor_tabs = QTabWidget()
        readings_tab = QWidget()
        readings_layout = QVBoxLayout(readings_tab)
        readings_layout.setContentsMargins(4, 12, 4, 4)
        readings_layout.setSpacing(14)

        connection_card, connection_layout = card()
        connection_layout.addWidget(label("Fonte das leituras", "sectionTitle"))
        connection_layout.addWidget(label(
            "Conecte em modo somente leitura para exibir medidas dos robôs. Nenhum comando de movimento é enviado.",
            "muted",
        ))
        connection_layout.addWidget(label(
            "Os IPs iniciais vêm do ur_rtde.py do projeto; confirme com Isma antes de conectar.",
            "muted",
        ))
        address_row = QHBoxLayout()
        self.ur3e_ip = QLineEdit("10.104.11.99")
        self.ur3e_ip.setPlaceholderText("IP do UR3e Leader")
        self.ur5e_ip = QLineEdit("10.104.11.71")
        self.ur5e_ip.setPlaceholderText("IP do UR5e Follower")
        address_row.addWidget(label("UR3e Leader"))
        address_row.addWidget(self.ur3e_ip, 1)
        address_row.addWidget(label("UR5e Follower"))
        address_row.addWidget(self.ur5e_ip, 1)
        connection_layout.addLayout(address_row)

        action_row = QHBoxLayout()
        self.connect_button = QPushButton("Conectar para ler medidas")
        self.connect_button.setObjectName("primary")
        self.connect_button.clicked.connect(self.connect_telemetry)
        self.demo_button = QPushButton("Testar demo 3D")
        self.demo_button.setObjectName("demo")
        self.demo_button.clicked.connect(self.start_demo)
        self.disconnect_button = QPushButton("Desconectar")
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self.disconnect_telemetry)
        action_row.addWidget(self.connect_button)
        action_row.addWidget(self.demo_button)
        action_row.addWidget(self.disconnect_button)
        self.telemetry_status = label("Desconectado • exibindo dados simulados", "badge")
        action_row.addWidget(self.telemetry_status, 1)
        connection_layout.addLayout(action_row)
        readings_layout.addWidget(connection_card)

        self.monitor_row = QHBoxLayout()
        self.monitor_row.setSpacing(16)
        self.monitor_row.addWidget(self.monitor_robot_card("UR3e", "LEADER"), 1)
        self.monitor_row.addWidget(self.monitor_robot_card("UR5e", "FOLLOWER"), 1)
        readings_layout.addLayout(self.monitor_row)
        readings_layout.addWidget(label(
            "Com RTDE conectado, as leituras são reais e somente de leitura. Sem conexão, os valores são simulados.",
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

        gripper_demo_row = QHBoxLayout()
        self.gripper_demo_button = QPushButton("Segure para abrir a garra (demo)")
        self.gripper_demo_button.setObjectName("demo")
        self.gripper_demo_button.setEnabled(False)
        self.gripper_demo_button.pressed.connect(self.open_demo_gripper)
        self.gripper_demo_button.released.connect(self.close_demo_gripper)
        gripper_demo_row.addWidget(self.gripper_demo_button)
        self.gripper_state_label = label("Garra do UR5e: fechada • demonstração", "badge")
        gripper_demo_row.addWidget(self.gripper_state_label, 1)
        visual_layout.addLayout(gripper_demo_row)

        self.expanded_camera = None
        self.view_splitter = QSplitter(Qt.Vertical)
        self.view_splitter.setChildrenCollapsible(False)
        self.visualization_card, visualization_layout = card()
        visualization_layout.addWidget(label("Modelos UR3e e UR5e", "sectionTitle"))
        self.visual_row = QHBoxLayout()
        self.visual_row.setSpacing(14)
        for robot_name, role in (("UR3e", "LEADER"), ("UR5e", "FOLLOWER")):
            panel = QFrame()
            panel.setObjectName("softPanel")
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(10, 9, 10, 8)
            panel_layout.setSpacing(4)
            panel_layout.addWidget(label(f"{robot_name}  ·  {role}", "sectionTitle"))
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

        self.monitor_tabs.addTab(readings_tab, "Leituras")
        self.monitor_tabs.addTab(visual_tab, "Visualização 3D + Câmeras")
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
        for robot_name in ("UR3e", "UR5e"):
            panel = self.robot_panels[robot_name]
            self.visual_row.removeWidget(panel)
            panel.setParent(None)
            robot_tabs.addTab(panel, robot_name)
        self._focus_robot_tabs = robot_tabs
        self.focus_overlay.set_robot_pip(robot_tabs)

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
            for _ in range(robot_tabs.count()):
                panel = robot_tabs.widget(0)
                robot_tabs.removeTab(0)
                panel.setParent(None)
                self.visual_row.addWidget(panel, 1)

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
        header.addWidget(label(name, "robotName"), 1)
        header.addWidget(label(role, "roleBadge"))
        layout.addLayout(header)
        source_label = label("Dados simulados • modo demonstração", "muted")
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

    def make_logs(self):
        layout = self.page("Logs", "Eventos da demonstração")
        widget, box = card()
        self.log_text = label("Sistema iniciado em modo demonstração.")
        box.addWidget(self.log_text)
        layout.addWidget(widget)
        layout.addStretch()

    def make_settings(self):
        layout = self.page("Configurações", "Informações gerais do protótipo")
        widget, box = card()
        box.addWidget(label("Conexão dos robôs", "robotName"))
        box.addWidget(label("As leituras RTDE são configuradas na tela Monitoramento."))
        box.addWidget(label("A interface usa somente RTDEReceive para telemetria; os botões de operação continuam simulados.", "muted"))
        layout.addWidget(widget)
        layout.addStretch()

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        for page_index, button in enumerate(self.nav):
            button.setChecked(page_index == index)

    def change_speed(self, value):
        self.speed = value
        self.speed_label.setText(f"{value}%")
        self.update_summary()

    def change_scale(self, value):
        self.scale = value
        for scale, button in self.scale_buttons:
            button.setObjectName("selected" if scale == value else "")
            button.style().unpolish(button)
            button.style().polish(button)
        self.update_summary()

    def update_summary(self):
        if hasattr(self, "summary_params"):
            scale = str(self.scale).replace(".", ",")
            self.summary_params.setText(f"Velocidade: {self.speed}%     |     Escala: {scale}×")

    def start(self):
        if self.telemetry_source is not None:
            self.operation_info.setText(
                "RTDE conectado somente para leitura. Este botão não movimenta o robô."
            )
            return
        self.running = True
        self.paused = False
        self.set_state("Simulação em andamento")
        self.add_log("Simulação iniciada")

    def start_demo(self):
        """Inicia a animação simulada sem tentar abrir comunicação com robôs."""
        if self.telemetry_source is not None:
            self.disconnect_telemetry("Demonstração ativa • sem conexão com robôs")
        self.t = 0.0
        self.running = True
        self.paused = False
        self.gripper_position = 255
        self.gripper_target = 255
        self.gripper_previous_position = 255
        self.gripper_demo_button.setEnabled(True)
        self.refresh_gripper_state("Demonstração")
        self.update_simulation()
        self.set_state("Demonstração em andamento")
        self.telemetry_status.setText("Demonstração ativa • dados simulados • sem robôs")
        for source_label in self.source_labels:
            source_label.setText("Demonstração • dados simulados")
        for status_label in self.status_labels:
            status_label.setText("Movimento: simulado")
        self.add_log("Modo demonstração iniciado; nenhum robô foi conectado")

    def pause(self):
        if self.telemetry_source is not None:
            self.operation_info.setText(
                "Pausar simulação não interrompe as leituras RTDE nem envia comandos ao robô."
            )
            return
        if not self.running:
            return
        self.paused = not self.paused
        state = "Simulação pausada" if self.paused else "Simulação em andamento"
        self.set_state(state)
        self.add_log("Simulação pausada" if self.paused else "Simulação retomada")

    def stop(self):
        if self.telemetry_source is not None:
            self.operation_info.setText(
                "Parar simulação não desconecta o RTDE. Use Desconectar em Monitoramento."
            )
            return
        self.running = False
        self.paused = False
        self.set_state("Operação parada")
        self.add_log("Simulação parada")

    def move_simulated_home(self):
        """Retorna a postura da demonstração à pose inicial definida na UI."""
        if self.telemetry_source is not None:
            self.operation_info.setText(
                "A conexão atual é somente de leitura. Home físico ainda não está integrado."
            )
            self.add_log("Home solicitado, mas não enviado: conexão RTDE é somente leitura")
            return

        self.running = False
        self.paused = False
        self.t = 0.0
        home_angles = [0.0, -90.0, 0.0, -90.0, 0.0, 0.0]
        for name in ("UR3e", "UR5e"):
            self.joint_angles[name] = list(home_angles)
        self.positions["UR3e"] = [180.0, -120.0, 250.0, 0.0, 3.142, 0.0]
        self.positions["UR5e"] = [350.0, -180.0, 400.0, 0.0, 3.142, 0.0]
        self.wrenches = {
            "UR3e": [0.0] * 6,
            "UR5e": [0.0] * 6,
        }
        self.set_state("Pose Home simulada")
        self.refresh_values()
        self.refresh_monitor()
        self.refresh_robot_views()
        self.add_log("Demonstração retornou à pose Home")

    def set_state(self, state):
        self.operation_info.setText(f"{state}. Nenhum robô real é controlado.")
        self.summary.setText(state)
        for item in self.status_labels:
            item.setText("Movimento: simulado" if self.running and not self.paused else "Movimento: parado")

    def add_log(self, text):
        old_lines = self.log_text.text().split("\n")
        self.log_text.setText("\n".join((old_lines + [text])[-12:]))

    def tick(self):
        if self.telemetry_source is not None:
            try:
                self.update_from_telemetry()
            except Exception as error:
                self.disconnect_telemetry(
                    f"Falha na leitura RTDE: {str(error)[:70]}"
                )
        elif self.running and not self.paused:
            self.update_simulation()
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

        self.connect_button.setEnabled(False)
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
            self.disconnect_button.setEnabled(True)
            self.gripper_demo_button.setEnabled(False)
            self.gripper_state_label.setText(
                "Garra: gPO não disponível na leitura RTDE atual"
            )
            self.telemetry_status.setText("Conectado • telemetria real, somente leitura")
            for source_label in self.source_labels:
                source_label.setText("RTDE • leitura real, somente leitura")
            for status_label in self.status_labels:
                status_label.setText("Telemetria conectada")
            self.add_log("Telemetria RTDE conectada (somente leitura)")
        except Exception as error:
            if source is not None:
                source.close()
            self.connect_button.setEnabled(True)
            self.telemetry_status.setText(f"Não conectou: {str(error)[:75]}")
            self.add_log("Falha ao conectar telemetria RTDE")

    def disconnect_telemetry(self, status="Desconectado • exibindo dados simulados"):
        source, self.telemetry_source = self.telemetry_source, None
        if source is not None:
            source.close()
        if hasattr(self, "connect_button"):
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.telemetry_status.setText(status)
            self.gripper_demo_button.setEnabled(self.running)
            if self.running:
                self.refresh_gripper_state("Demonstração")
            else:
                self.gripper_state_label.setText(
                    "Garra: estado simulado • inicie a demo para testar"
                )
            for source_label in self.source_labels:
                source_label.setText("Dados simulados • modo demonstração")
            for status_label in self.status_labels:
                status_label.setText("Movimento: parado")
        self.add_log("Telemetria RTDE desconectada")

    def update_simulation(self):
        self.t += 0.1 * self.speed / 50
        dx = 35 * math.sin(self.t * 0.7)
        dy = 25 * math.cos(self.t * 0.5)
        dz = 18 * math.sin(self.t * 0.4)
        self.positions["UR3e"][:3] = [180 + dx, -120 + dy, 250 + dz]
        self.positions["UR5e"][:3] = [
            350 + self.scale * dx,
            -180 + self.scale * dy,
            400 + self.scale * dz,
        ]
        self.update_simulated_feedback()
        self.advance_demo_gripper()

    def update_from_telemetry(self):
        """Atualiza a interface com uma fonte RTDE somente de leitura."""
        samples = self.telemetry_source.read()
        for name in ("UR3e", "UR5e"):
            sample = samples[name]
            self.joint_angles[name] = [math.degrees(value) for value in sample.joint_positions_rad]
            pose = sample.tcp_pose_m_rad
            self.positions[name] = [pose[0] * 1000, pose[1] * 1000, pose[2] * 1000, *pose[3:]]
            self.wrenches[name] = list(sample.tcp_wrench_n_nm)

    def open_demo_gripper(self):
        """Botão pressionado: abre a garra apenas na demonstração 3D."""
        if not self.running or self.telemetry_source is not None:
            return
        self.gripper_target = 0

    def close_demo_gripper(self):
        """Botão solto: fecha a garra apenas na demonstração 3D."""
        if not self.running or self.telemetry_source is not None:
            return
        self.gripper_target = 255

    def advance_demo_gripper(self):
        if self.telemetry_source is not None:
            return
        previous = self.gripper_position
        step = 16
        if previous < self.gripper_target:
            self.gripper_position = min(self.gripper_target, previous + step)
        elif previous > self.gripper_target:
            self.gripper_position = max(self.gripper_target, previous - step)
        if self.gripper_position != previous:
            direction = "Abrindo" if self.gripper_position < previous else "Fechando"
            if self.gripper_position == 0:
                direction = "Aberta"
            elif self.gripper_position == 255:
                direction = "Fechada"
            self.refresh_gripper_state(direction)

    def refresh_gripper_state(self, state):
        percent_closed = round(100 * self.gripper_position / 255)
        self.gripper_state_label.setText(
            f"Garra do UR5e: {state} • {percent_closed}% fechada • demo"
        )

    def set_telemetry_source(self, source):
        """Injeta um leitor já conectado. Não conecta automaticamente ao robô."""
        self.telemetry_source = source

    def closeEvent(self, event):
        if self.telemetry_source is not None:
            self.telemetry_source.close()
        for camera_panel in getattr(self, "camera_panels", []):
            camera_panel.stop_camera()
        super().closeEvent(event)

    def update_simulated_feedback(self):
        t = self.t
        self.joint_angles["UR3e"] = [
            12 * math.sin(t * 0.35),
            -90 + 8 * math.sin(t * 0.55),
            10 * math.cos(t * 0.45),
            -90 + 5 * math.sin(t * 0.30),
            4 * math.cos(t * 0.40),
            8 * math.sin(t * 0.25),
        ]
        self.joint_angles["UR5e"] = [
            8 * math.sin(t * 0.32),
            -90 + 6 * math.sin(t * 0.50),
            8 * math.cos(t * 0.42),
            -90 + 4 * math.sin(t * 0.28),
            3 * math.cos(t * 0.36),
            6 * math.sin(t * 0.22),
        ]
        for robot, factor in (("UR3e", 1.0), ("UR5e", 0.7)):
            self.wrenches[robot] = [
                factor * 3.0 * math.sin(t * 0.7),
                factor * 2.0 * math.cos(t * 0.5),
                factor * 4.0 * math.sin(t * 0.4),
                factor * 0.25 * math.sin(t * 0.6),
                factor * 0.20 * math.cos(t * 0.45),
                factor * 0.30 * math.sin(t * 0.35),
            ]

    def refresh_values(self):
        for name, position in self.positions.items():
            for index, value in enumerate(position):
                formatted = f"{value:.1f}" if index < 3 else f"{value:.3f}"
                self.values[(name, index)].setText(formatted)

    def refresh_monitor(self):
        if not self.monitor_values:
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
        follower_view = self.robot_views.get("UR5e")
        if follower_view is not None:
            follower_view.set_gripper_position(self.gripper_position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.camera_focus_active:
            self.focus_overlay.setGeometry(self.rect())
            self.focus_overlay.raise_()
        if hasattr(self, "robot_row"):
            narrow = self.width() < 930
            direction = QVBoxLayout.TopToBottom if narrow else QHBoxLayout.LeftToRight
            self.robot_row.setDirection(direction)
            self.monitor_row.setDirection(direction)
            if hasattr(self, "visual_row"):
                self.visual_row.setDirection(direction)
            if hasattr(self, "camera_row"):
                self.camera_row.setDirection(direction)
            self.sidebar.setFixedWidth(170 if narrow else 222)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ELO()
    window.show()
    sys.exit(app.exec())
