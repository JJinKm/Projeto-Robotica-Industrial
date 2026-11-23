"""Painel de vídeo USB embutido na interface AEGIS."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class CameraPanel(QFrame):
    """Exibe uma câmera selecionada pelo usuário, sem abrir vídeo ao iniciar o app."""

    expandRequested = Signal(object)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("softPanel")
        self.devices = []
        self.camera = None
        self.capture_session = None
        self.media_devices = QMediaDevices(self)
        self.media_devices.videoInputsChanged.connect(self.refresh_devices)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 11, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(title)
        header.addWidget(self.title_label, 1)
        self.refresh_button = QPushButton("Atualizar câmeras")
        self.refresh_button.clicked.connect(self.refresh_devices)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        controls = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(150)
        self.start_button = QPushButton("Abrir câmera")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_camera)
        self.expand_button = QPushButton("Ampliar")
        self.expand_button.clicked.connect(lambda: self.expandRequested.emit(self))
        self.stop_button = QPushButton("Fechar")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_camera)
        controls.addWidget(self.device_combo, 1)
        controls.addWidget(self.start_button)
        controls.addWidget(self.expand_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(200)
        self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
        self.video_widget.setStyleSheet("background:#07170F; border:1px solid #214832; border-radius:10px;")
        layout.addWidget(self.video_widget, 1)

        self.status_label = QLabel("Câmera fechada • selecione um dispositivo USB")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self._normal_video_minimum = 200
        self.refresh_devices()

    def set_focus_mode(self, mode):
        """Ajusta o painel para ocupar a tela ou aparecer em uma janela PiP."""
        compact = mode == "pip"
        self.refresh_button.setVisible(not compact)
        self.status_label.setVisible(not compact)
        self.video_widget.setMinimumHeight(120 if compact else self._normal_video_minimum)
        if mode == "main":
            self.expand_button.setText("Voltar")
        else:
            self.expand_button.setText("Ampliar")

    def restore_normal_mode(self):
        self.set_focus_mode("normal")

    def refresh_devices(self):
        selected_id = self.device_combo.currentData()
        self.devices = list(QMediaDevices.videoInputs())
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for device in self.devices:
            self.device_combo.addItem(device.description(), bytes(device.id()))
        if selected_id is not None:
            index = self.device_combo.findData(selected_id)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)
        self.device_combo.blockSignals(False)

        has_devices = bool(self.devices)
        self.device_combo.setEnabled(has_devices and self.camera is None)
        self.start_button.setEnabled(has_devices and self.camera is None)
        if not has_devices:
            self.status_label.setText(
                "Nenhuma câmera encontrada. Conecte a webcam/câmera USB e atualize a lista."
            )
        elif self.camera is None:
            self.status_label.setText("Câmeras encontradas • selecione uma e clique em Abrir câmera")

    def start_camera(self):
        index = self.device_combo.currentIndex()
        if index < 0 or index >= len(self.devices):
            self.status_label.setText("Selecione uma câmera disponível.")
            return

        try:
            device = self.devices[index]
            camera = QCamera(device, self)
            session = QMediaCaptureSession(self)
            session.setCamera(camera)
            session.setVideoOutput(self.video_widget)
            camera.errorOccurred.connect(self._camera_error)
            camera.activeChanged.connect(self._camera_active_changed)
            self.camera = camera
            self.capture_session = session
            camera.start()
            self.device_combo.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setText(f"Abrindo: {device.description()}")
        except Exception as error:
            self.status_label.setText(f"Não foi possível abrir a câmera: {str(error)[:120]}")

    def _camera_error(self, error, description):
        if error:
            self.status_label.setText(
                f"Falha na câmera: {description or 'verifique a permissão do Windows e o cabo USB.'}"
            )

    def _camera_active_changed(self, active):
        if active:
            self.status_label.setText("Câmera ativa • vídeo exibido nesta tela")

    def stop_camera(self):
        camera, self.camera = self.camera, None
        session, self.capture_session = self.capture_session, None
        if camera is not None:
            camera.stop()
            camera.deleteLater()
        if session is not None:
            session.deleteLater()
        self.device_combo.setEnabled(bool(self.devices))
        self.refresh_button.setEnabled(True)
        self.start_button.setEnabled(bool(self.devices))
        self.stop_button.setEnabled(False)
        self.status_label.setText("Câmera fechada")

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)
