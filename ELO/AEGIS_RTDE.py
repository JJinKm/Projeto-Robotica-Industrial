"""Entrada do AEGIS conectada ao controlador RTDE do Joshua.

Iniciar abre as conexões RTDE e ativa a garra. Home move os dois robôs à pose
definida no script e, ao terminar, habilita o UR5e para acompanhar o UR3e, com
o leader em force mode, reflexão de força do follower e a garra no botão da
ferramenta (mesma lógica do ur_rtde.py). Parar (ou a tecla Espaço) interrompe
tudo, inclusive um Home em andamento.
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


# --- Configuração do controle (valores do ur_rtde.py) ----------------------
# "forca": leader em force mode nativo do UR (sensor F/T do UR3e) com reflexão
#          da força estimada no follower; "teach": freedrive simples.
MODO_GUIA = "forca"
AMORTECIMENTO = 0.015  # 0..1  maior = para mais rápido ao soltar
GANHO_FORCA = 2.0      # 0..2  maior = responde mais rápido ao empurrão
VMAX_LIN = 0.25        # m/s
VMAX_ROT = 0.8         # rad/s

# Troca teach/force no leader pela força lida no sensor dele.
F_ENTRA_FORCE = 1.1    # N  acima disso o leader vai p/ force mode
F_SAI_FORCE = 0.5      # N  (não usado na lógica atual do ur_rtde.py)

# Reflexão de força follower -> leader (estimativa do CB3, ruído 15-40 N).
REFLEXAO = True
K_REFLEXAO = 0.1            # N no leader por N no follower
ZONA_MORTA_REFLEXAO = 30.0  # N
FMAX_REFLEXAO = 10.0        # N
ALFA_REFLEXAO = 0.1         # filtro (menor = mais suave)
T_CALIBRACAO = 1.5          # s

# Garra: botão na entrada digital 16 do leader (ferramenta).
BOTAO_GARRA = 16
POS_ABERTA_GARRA = 100

# Home
JOINT_HOME = [-1.57, -1.57, -1.57, -1.57, 1.57, 0.0]
VEL_HOME = 1.5    # rad/s
ACEL_HOME = 0.5   # rad/s²


class _ParadaSolicitada(Exception):
    """Parar foi pressionado durante uma etapa bloqueante (ex.: Home)."""


class _JoshuaRTDEWorker(QThread):
    """Executa a lógica RTDE fora da thread da interface gráfica.

    Estados emitidos em state_changed: conectando, conectado, home,
    acompanhando, pausado, parando, erro.
    """

    status_changed = Signal(str, str)   # mensagem, nível (info|aviso|erro)
    state_changed = Signal(str)
    info_changed = Signal(dict)         # indicadores: leader, força, reflexão, garra

    def __init__(self, master_ip: str, follower_ip: str):
        super().__init__()
        self.master_ip = master_ip
        self.follower_ip = follower_ip
        self.estado = "conectando"
        self._stop_requested = threading.Event()
        self._pause_requested = threading.Event()
        self._tracking_ready = threading.Event()
        self._commands: queue.Queue[str] = queue.Queue()
        self._info = {"leader": "—", "f_follower": None, "reflexao": "—", "garra": "—"}

    # --- comandos vindos da interface (thread da GUI) ---------------------
    def request_stop(self):
        self._stop_requested.set()

    def toggle_pause(self):
        if not self._tracking_ready.is_set():
            return
        if self._pause_requested.is_set():
            self._pause_requested.clear()
        else:
            self._pause_requested.set()

    def request_home(self):
        self._commands.put("home")

    # --- auxiliares --------------------------------------------------------
    def _status(self, texto, nivel="info"):
        self.status_changed.emit(texto, nivel)

    def _estado(self, estado):
        if estado != self.estado:
            self.estado = estado
            self.state_changed.emit(estado)

    def _info_set(self, **valores):
        mudou = any(self._info.get(k) != v for k, v in valores.items())
        self._info.update(valores)
        if mudou:
            self.info_changed.emit(dict(self._info))

    @staticmethod
    def _try_call(obj, method_name, *args):
        if obj is None:
            return
        method = getattr(obj, method_name, None)
        if method is not None:
            try:
                method(*args)
            except Exception:
                pass

    def _mover_home(self, ctrl, nome):
        """moveJ assíncrono: Parar interrompe o movimento com stopJ."""
        self._status(f"Movendo o {nome} para Home...")
        ctrl.moveJ(JOINT_HOME, VEL_HOME, ACEL_HOME, True)
        time.sleep(0.1)
        while ctrl.getAsyncOperationProgressEx().isAsyncOperationRunning():
            if self._stop_requested.is_set():
                ctrl.stopJ(2.0)
                raise _ParadaSolicitada()
            if not ctrl.isProgramRunning():
                raise RuntimeError(f"O script do {nome} parou durante o Home (protective stop?).")
            time.sleep(0.02)

    # --- Leader: force mode + reflexão de força (mesma lógica do ur_rtde.py) ---
    def _passo_forca(self, mc, w_lin=(0.0, 0.0, 0.0)):
        mc.forceMode(
            [0, 0, 0, 0, 0, 0],                 # referencial: base
            [1, 1, 1, 1, 1, 1],                 # todos os eixos complacentes
            list(w_lin) + [0.0, 0.0, 0.0],      # força alvo = reflexão (torque zero)
            2,                                  # referencial não transformado
            [VMAX_LIN] * 3 + [VMAX_ROT] * 3,    # limites de velocidade
        )

    def _forca_reflexao(self, fr, f_filt, vies):
        f = [a - b for a, b in zip(fr.getActualTCPForce()[:3], vies)]
        f_filt = [(1 - ALFA_REFLEXAO) * a + ALFA_REFLEXAO * b for a, b in zip(f_filt, f)]
        norma = math.sqrt(sum(x * x for x in f_filt))
        mag = min(K_REFLEXAO * max(norma - ZONA_MORTA_REFLEXAO, 0.0), FMAX_REFLEXAO)
        w = [mag * x / norma for x in f_filt] if mag > 0 else [0.0, 0.0, 0.0]
        return w, f_filt, norma, mag

    def _conectar_garra(self):
        try:
            try:
                from garra_robotiq import Garra
            except ImportError:
                from .garra_robotiq import Garra
            garra = Garra()
        except Exception as error:
            self._status(f"Garra indisponível ({error}). Seguindo sem garra.", "aviso")
            self._info_set(garra="indisponível")
            return None
        self._status(
            f"Conectando à garra na {garra.porta} (aguarde ~10 s, o USB da câmera reinicia)..."
        )
        try:
            garra.conectar(cancelar=self._stop_requested.is_set)
            garra.ativar()
            garra.mover(POS_ABERTA_GARRA)
            garra.fechada = False
            self._status(f"Garra ativa na {garra.porta}.")
            self._info_set(garra="aberta")
            return garra
        except Exception as error:
            garra.fechar_porta()
            if self._stop_requested.is_set():
                raise _ParadaSolicitada()
            self._status(f"Garra indisponível ({error}). Seguindo sem garra.", "aviso")
            self._info_set(garra="indisponível")
            return None

    def run(self):
        master_control = master_receive = None
        follower_control = follower_receive = None
        garra = None
        teach_mode = False
        force_mode = False
        servo_active = False

        def leader_parado():
            """Tira o leader do teach/force mode; ele fica travado na pose."""
            nonlocal teach_mode, force_mode
            if force_mode:
                master_control.forceModeStop()
                force_mode = False
            if teach_mode:
                master_control.endTeachMode()
                teach_mode = False
            self._info_set(leader="travado")

        try:
            from rtde_control import RTDEControlInterface as RTDEControl
            from rtde_receive import RTDEReceiveInterface as RTDEReceive

            self._estado("conectando")
            self._status("Conectando aos controladores RTDE...")
            master_control = RTDEControl(self.master_ip)
            master_receive = RTDEReceive(self.master_ip)
            follower_control = RTDEControl(self.follower_ip)
            follower_receive = RTDEReceive(self.follower_ip)
            self._status("RTDE conectado aos dois robôs.")
            self._info_set(leader="travado", reflexao="desligada" if not REFLEXAO else "inativa")

            if self._stop_requested.is_set():
                raise _ParadaSolicitada()
            garra = self._conectar_garra()

            self._estado("conectado")
            self._status("Pronto. Pressione Home para posicionar os robôs e iniciar o acompanhamento.")

            dt = 0.008
            lookahead_time = 0.1
            gain = 300
            paused_on_robot = False
            next_info_at = 0.0

            # Estado da reflexão de força (recalibrado a cada Home/retomada).
            f_filt = [0.0, 0.0, 0.0]
            f_mag = 0.0
            vies_follower = None
            amostras_vies = []
            t_calib = None

            def reiniciar_calibracao():
                nonlocal f_filt, vies_follower, amostras_vies, t_calib
                f_filt = [0.0, 0.0, 0.0]
                vies_follower = None
                amostras_vies = []
                t_calib = None

            while not self._stop_requested.is_set():
                # Processa Home na mesma thread que controla os robôs.
                try:
                    command = self._commands.get_nowait()
                except queue.Empty:
                    command = None

                if command == "home":
                    self._estado("home")
                    self._tracking_ready.clear()
                    if servo_active:
                        follower_control.servoStop()
                        servo_active = False
                    leader_parado()
                    self._mover_home(master_control, "UR3e (leader)")
                    self._mover_home(follower_control, "UR5 (follower)")
                    if MODO_GUIA == "forca":
                        self._status("Zerando o sensor de força do leader: não encoste nos robôs...", "aviso")
                        time.sleep(0.5)
                        master_control.zeroFtSensor()
                        time.sleep(0.2)
                        master_control.forceModeSetDamping(AMORTECIMENTO)
                        master_control.forceModeSetGainScaling(GANHO_FORCA)
                        reiniciar_calibracao()
                    else:
                        master_control.teachMode()
                        teach_mode = True
                        self._info_set(leader="teach")
                    self._pause_requested.clear()
                    self._tracking_ready.set()
                    paused_on_robot = False
                    self._estado("acompanhando")
                    self._status("Home concluído; o UR5 está acompanhando o UR3e.")

                if not self._tracking_ready.is_set():
                    self.msleep(20)
                    continue

                if self._pause_requested.is_set():
                    if not paused_on_robot:
                        if servo_active:
                            follower_control.servoStop()
                            servo_active = False
                        # Trava o leader para o follower não dar um salto ao retomar.
                        leader_parado()
                        paused_on_robot = True
                        self._estado("pausado")
                        self._status("Acompanhamento pausado: leader travado, follower parado.", "aviso")
                    self.msleep(20)
                    continue

                if paused_on_robot:
                    paused_on_robot = False
                    if MODO_GUIA == "forca":
                        reiniciar_calibracao()
                    else:
                        master_control.teachMode()
                        teach_mode = True
                        self._info_set(leader="teach")
                    self._estado("acompanhando")
                    self._status("Acompanhamento retomado.")

                period_start = follower_control.initPeriod()

                if garra is not None:
                    msg = garra.atualizar_botao(master_receive.getDigitalInState(BOTAO_GARRA))
                    if msg:
                        ok = not msg.startswith("Aviso")
                        self._status(msg, "info" if ok else "aviso")
                        self._info_set(garra="fechada" if garra.fechada else "aberta")

                joint_master = master_receive.getActualQ()

                if MODO_GUIA == "forca":
                    if REFLEXAO and vies_follower is None:
                        # Mede o viés da estimativa de força com o follower servoando.
                        if t_calib is None:
                            t_calib = time.monotonic()
                            self._info_set(reflexao="calibrando")
                            self._status(
                                f"Calibrando a força do follower por {T_CALIBRACAO} s: "
                                "não encoste no follower...", "aviso"
                            )
                        amostras_vies.append(follower_receive.getActualTCPForce()[:3])
                        if time.monotonic() - t_calib >= T_CALIBRACAO:
                            n = len(amostras_vies)
                            vies_follower = [sum(a[i] for a in amostras_vies) / n for i in range(3)]
                            self._info_set(reflexao="inativa")
                            self._status("Calibração concluída. Reflexão de força ativa.")
                        if teach_mode:
                            master_control.endTeachMode()
                            teach_mode = False
                        self._passo_forca(master_control)
                        force_mode = True
                        self._info_set(leader="força")
                    elif REFLEXAO:
                        w_ref, f_filt, f_mag, mag_ref = self._forca_reflexao(
                            follower_receive, f_filt, vies_follower
                        )
                        f_lider = math.sqrt(
                            sum(x * x for x in master_receive.getActualTCPForce()[:3])
                        )
                        # Mão no leader -> force mode; senão teach mode, que não deriva parado.
                        if f_lider > F_ENTRA_FORCE:
                            if teach_mode:
                                master_control.endTeachMode()
                                teach_mode = False
                            self._passo_forca(master_control, w_ref)
                            force_mode = True
                            self._info_set(leader="força")
                        elif not teach_mode:
                            if force_mode:
                                master_control.forceModeStop()
                                force_mode = False
                            master_control.teachMode()
                            teach_mode = True
                            self._info_set(leader="teach")
                        self._info_set(reflexao="refletindo" if mag_ref > 0 else "inativa")
                    else:
                        self._passo_forca(master_control)
                        force_mode = True
                        self._info_set(leader="força")

                # Se o script de algum robô morreu (ex.: protective stop), para tudo.
                if not (master_control.isProgramRunning() and follower_control.isProgramRunning()):
                    raise RuntimeError(
                        "O script de controle parou em um dos robôs (protective stop?). "
                        "Feche o aviso no pendant e pressione Iniciar de novo."
                    )

                follower_control.servoJ(joint_master, 0, 0, dt, lookahead_time, gain)
                servo_active = True
                follower_control.waitPeriod(period_start)

                now = time.monotonic()
                if now >= next_info_at:
                    self._info_set(f_follower=round(f_mag))
                    next_info_at = now + 0.25

            self._estado("parando")
            self._status("Parada solicitada: encerrando o controle dos robôs.", "aviso")

        except _ParadaSolicitada:
            self._estado("parando")
            self._status("Parada solicitada: movimento interrompido.", "aviso")
        except Exception as error:
            self._estado("erro")
            self._status(f"Falha no controle: {error}", "erro")
        finally:
            if garra is not None:
                garra.fechar_porta()
            self._try_call(follower_control, "servoStop")
            if force_mode:
                self._try_call(master_control, "forceModeStop")
            if teach_mode:
                self._try_call(master_control, "endTeachMode")
            self._tracking_ready.clear()
            self._try_call(follower_control, "stopScript")
            self._try_call(master_control, "stopScript")
            self._try_call(master_receive, "disconnect")
            self._try_call(follower_receive, "disconnect")
            self._try_call(master_control, "disconnect")
            self._try_call(follower_control, "disconnect")
            self._info_set(leader="—", f_follower=None, reflexao="—", garra="—")
            if self.estado != "erro":  # não apaga a mensagem de erro da tela
                self._status("Controle dos robôs desconectado.")


class JoshuaController(QObject):
    """Faz a ponte entre os sinais do AEGIS e o worker RTDE."""

    status_changed = Signal(str, str)
    state_changed = Signal(str)
    info_changed = Signal(dict)

    def __init__(self, master_ip: str, follower_ip: str):
        super().__init__()
        self.master_ip = master_ip
        self.follower_ip = follower_ip
        self.worker: _JoshuaRTDEWorker | None = None

    def ativo(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def iniciar(self):
        if self.ativo():
            return
        self.worker = _JoshuaRTDEWorker(self.master_ip, self.follower_ip)
        self.worker.status_changed.connect(self.status_changed)
        self.worker.state_changed.connect(self.state_changed)
        self.worker.info_changed.connect(self.info_changed)
        self.worker.finished.connect(self._ao_terminar)
        self.state_changed.emit("conectando")
        self.worker.start()

    def _ao_terminar(self):
        worker = self.sender()
        if worker is not None and worker.estado == "erro":
            return  # mantém o estado de erro visível até o próximo Iniciar
        self.state_changed.emit("desconectado")

    def alternar_pausa(self):
        if self.ativo():
            self.worker.toggle_pause()

    def ir_para_home(self):
        if self.ativo():
            self.worker.request_home()

    def parar(self):
        """Não bloqueia a interface: o worker encerra e emite o estado final."""
        if self.ativo():
            self.state_changed.emit("parando")
            self.worker.request_stop()

    def encerrar(self):
        if self.ativo():
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
                    "Iniciar conecta os robôs e a garra. Home move os dois robôs para a pose "
                    "inicial e começa o acompanhamento. Parar (Espaço) interrompe tudo."
                )
        self.controlador = JoshuaController(
            master_ip=self.ur3e_ip.text().strip(),
            follower_ip=self.ur5e_ip.text().strip(),
        )
        self.controlador.status_changed.connect(self._mostrar_status_rtde)
        self.controlador.state_changed.connect(self.apply_operation_state)
        self.controlador.info_changed.connect(self.set_indicators)

        self.iniciar_solicitado.connect(self.controlador.iniciar)
        self.pausar_retomar_solicitado.connect(self.controlador.alternar_pausa)
        self.home_solicitado.connect(self.controlador.ir_para_home)
        self.parar_solicitado.connect(self.controlador.parar)
        self.set_message("Pronto. Pressione Iniciar para conectar os robôs.")

    def _mostrar_status_rtde(self, text: str, nivel: str):
        self.add_log(text, nivel)
        self.set_message(text, nivel)

    def _solicitar_inicio(self):
        self.controlador.master_ip = self.ur3e_ip.text().strip()
        self.controlador.follower_ip = self.ur5e_ip.text().strip()
        self.iniciar_solicitado.emit()
        # Também conecta a telemetria (juntas, TCP e forças na tela).
        self.connect_telemetry()

    def _confirmar_home(self):
        resposta = QMessageBox.warning(
            self,
            "Confirmar movimento para Home",
            "Home movimentará os dois robôs para a posição definida no script. "
            "Quando terminar, o UR5 começará a acompanhar o UR3e. "
            "Confirme que o trajeto está livre.\n\n"
            "Durante o movimento, Parar (Espaço) interrompe os robôs.",
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
