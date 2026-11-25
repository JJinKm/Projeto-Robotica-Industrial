"""Entrada do AEGIS conectada ao controlador RTDE do Joshua.

Iniciar apenas abre as conexões RTDE. Home move os dois robôs à pose definida
no script e, ao terminar, habilita o UR5e para acompanhar o UR3e.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import math

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

try:  # Permite executar como arquivo ou importar como pacote.
    from .Projeto_Robotica import AegisApp
except ImportError:
    from Projeto_Robotica import AegisApp


class _JoshuaRTDEWorker(QThread):
    """Executa a lógica RTDE fora da thread da interface gráfica."""

    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, master_ip: str, follower_ip: str):
        super().__init__()
        self.master_ip = master_ip
        self.follower_ip = follower_ip
        self._stop_requested = threading.Event()
        self._pause_requested = threading.Event()
        self._tracking_ready = threading.Event()
        self._commands: queue.Queue[str] = queue.Queue()

    def request_stop(self):
        self._stop_requested.set()

    def toggle_pause(self):
        if not self._tracking_ready.is_set():
            self.status_changed.emit("Pressione Home antes de pausar ou retomar.")
            return
        if self._pause_requested.is_set():
            self._pause_requested.clear()
            self.status_changed.emit("Retomando o acompanhamento do UR3e.")
        else:
            self._pause_requested.set()
            self.status_changed.emit("Pausa solicitada.")

    def request_home(self):
        self._commands.put("home")

    @staticmethod
    def _try_call(obj, method_name):
        if obj is None:
            return
        method = getattr(obj, method_name, None)
        if method is not None:
            try:
                method()
            except Exception:
                pass

    def run(self):
        master_control = master_receive = None
        follower_control = follower_receive = None
        teach_mode = False
        servo_active = False

        try:
            from rtde_control import RTDEControlInterface as RTDEControl
            from rtde_receive import RTDEReceiveInterface as RTDEReceive

            self.status_changed.emit("Conectando aos controladores RTDE...")
            master_control = RTDEControl(self.master_ip)
            master_receive = RTDEReceive(self.master_ip)
            follower_control = RTDEControl(self.follower_ip)
            follower_receive = RTDEReceive(self.follower_ip)

            self.status_changed.emit(
                "RTDE conectado. Pressione Home para posicionar os robôs e iniciar o acompanhamento."
            )

            # A pose do Joshua só é comandada quando a pessoa pressiona Home.
            joint_home = [-1.57, -1.57, -1.57, -1.57, 1.57, 0.0]
            dt = 0.008
            lookahead_time = 0.1
            gain = 300
            paused_on_robot = False
            next_status_at = 0.0

            while not self._stop_requested.is_set():
                # Processa Home na mesma thread que controla os robôs.
                try:
                    command = self._commands.get_nowait()
                except queue.Empty:
                    command = None

                if command == "home":
                    self.status_changed.emit("Movendo os dois robôs para Home...")
                    if servo_active:
                        follower_control.servoStop()
                        servo_active = False
                    if teach_mode:
                        master_control.endTeachMode()
                        teach_mode = False
                    master_control.moveJ(joint_home, 1.5, 0.5)
                    follower_control.moveJ(joint_home, 1.5, 0.5)
                    if not self._stop_requested.is_set():
                        master_control.teachMode()
                        teach_mode = True
                        self._pause_requested.clear()
                        self._tracking_ready.set()
                    paused_on_robot = False
                    self.status_changed.emit(
                        "Home concluído; iniciando envio de comandos de acompanhamento ao UR5e."
                    )

                if not self._tracking_ready.is_set():
                    self.msleep(20)
                    continue

                if self._pause_requested.is_set():
                    if servo_active:
                        follower_control.servoStop()
                        servo_active = False
                        paused_on_robot = True
                        self.status_changed.emit("Acompanhamento pausado.")
                    self.msleep(20)
                    continue

                if paused_on_robot:
                    paused_on_robot = False
                    self.status_changed.emit("Acompanhamento retomado.")

                period_start = follower_control.initPeriod()
                joint_master = master_receive.getActualQ()
                joint_follower = follower_receive.getActualQ()
                follower_control.servoJ(
                    joint_master, 0, 0, dt, lookahead_time, gain
                )
                servo_active = True
                follower_control.waitPeriod(period_start)

                # Diagnóstico: reporta posições medidas, sem afirmar que o
                # seguidor acompanhou até observar mudança na leitura real.
                now = time.monotonic()
                if now >= next_status_at:
                    master_deg = ", ".join(f"{math.degrees(q):.1f}" for q in joint_master)
                    follower_deg = ", ".join(f"{math.degrees(q):.1f}" for q in joint_follower)
                    self.status_changed.emit(
                        f"RTDE ativo | UR3e [°]: {master_deg} | UR5e [°]: {follower_deg}"
                    )
                    next_status_at = now + 1.0

        except Exception as error:
            self.error_occurred.emit(f"Falha no controle RTDE: {error}")
        finally:
            self.status_changed.emit("Encerrando o controle RTDE com servoStop.")
            self._try_call(follower_control, "servoStop")
            if teach_mode:
                self._try_call(master_control, "endTeachMode")
            self._try_call(follower_control, "stopScript")
            self._try_call(master_control, "stopScript")
            self._try_call(master_receive, "disconnect")
            self._try_call(follower_receive, "disconnect")
            self._try_call(master_control, "disconnect")
            self._try_call(follower_control, "disconnect")
            self.status_changed.emit("Controlador RTDE desconectado.")


class JoshuaController(QObject):
    """Faz a ponte entre os sinais do AEGIS e o worker RTDE."""

    status_changed = Signal(str)

    def __init__(self, master_ip: str, follower_ip: str):
        super().__init__()
        self.master_ip = master_ip
        self.follower_ip = follower_ip
        self.worker: _JoshuaRTDEWorker | None = None

    def iniciar(self):
        if self.worker is not None and self.worker.isRunning():
            self.status_changed.emit(
                "RTDE já está conectado. Pressione Home para iniciar o movimento."
            )
            return
        self.worker = _JoshuaRTDEWorker(self.master_ip, self.follower_ip)
        self.worker.status_changed.connect(self.status_changed)
        self.worker.error_occurred.connect(self.status_changed)
        self.worker.start()

    def alternar_pausa(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.toggle_pause()

    def ir_para_home(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_home()
        else:
            self.status_changed.emit("Pressione Iniciar para conectar antes de solicitar Home.")

    def encerrar(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait()


class AegisRTDEApp(AegisApp):
    """AEGIS com botões físicos conectados ao controlador do Joshua."""

    def __init__(self):
        super().__init__()
        # Atualiza as instruções da tela herdada para o fluxo físico.
        for widget in self.findChildren(QLabel):
            if widget.text().startswith("Os botões ainda não enviam comandos"):
                widget.setText(
                    "Iniciar apenas conecta. Home move os dois robôs para a pose inicial; "
                    "depois o programa envia comandos para o UR5e copiar o UR3e."
                )
        self.controlador = JoshuaController(
            master_ip=self.ur3e_ip.text().strip(),
            follower_ip=self.ur5e_ip.text().strip(),
        )
        self.controlador.status_changed.connect(self._mostrar_status_rtde)

        self.iniciar_solicitado.connect(self.controlador.iniciar)
        self.pausar_retomar_solicitado.connect(self.controlador.alternar_pausa)
        self.home_solicitado.connect(self.controlador.ir_para_home)
        self.operation_info.setText("Pronto. Iniciar conecta; Home inicia o movimento.")

    def _mostrar_status_rtde(self, text: str):
        self.add_log(text)
        self.operation_info.setText(text)
        self.summary.setText(text)

    def _solicitar_inicio(self):
        # Iniciar estabelece comunicação, sem chamar moveJ ou servoJ.
        self.controlador.master_ip = self.ur3e_ip.text().strip()
        self.controlador.follower_ip = self.ur5e_ip.text().strip()
        self.iniciar_solicitado.emit()

    def _solicitar_pausa_retomada(self):
        self.pausar_retomar_solicitado.emit()

    def _confirmar_home(self):
        resposta = QMessageBox.warning(
            self,
            "Confirmar movimento para Home",
            "Home movimentará os dois robôs para a posição definida no script. "
            "Quando terminar, o UR5e começará a acompanhar o UR3e. "
            "Confirme que o trajeto está livre.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            self.home_solicitado.emit()

    def closeEvent(self, event):
        self.controlador.encerrar()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = AegisRTDEApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
