"""Entrada do AEGIS conectada ao controlador RTDE do Joshua.

Iniciar abre as conexões RTDE e ativa a garra. Home move os dois robôs à pose
definida no script e, ao terminar, habilita o UR5e para acompanhar o UR3e, com
o leader em force mode, reflexão de força do follower e a garra no botão da
ferramenta (mesma lógica do ur_rtde.py). Parar (ou a tecla Espaço) interrompe
tudo, inclusive um Home em andamento.
"""

from __future__ import annotations

import queue
import socket
import sys
import threading
import time
import math

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

try:  # Permite executar como arquivo ou importar como pacote.
    from . import aegis_config
    from .Projeto_Robotica import AegisApp
    from .rtde_telemetry import RobotTelemetry
    from .sensor_leader import ModeloSensorLeader
except ImportError:
    import aegis_config
    from Projeto_Robotica import AegisApp
    from rtde_telemetry import RobotTelemetry
    from sensor_leader import ModeloSensorLeader


# --- Configuração do controle (valores do ur_rtde.py) ----------------------
# "forca": leader em force mode nativo do UR (sensor F/T do UR3e) com reflexão
#          da força estimada no follower; "teach": freedrive simples.
MODO_GUIA = "forca"
VMAX_LIN = 0.25        # m/s
VMAX_ROT = 0.8         # rad/s
# Amortecimento, ganho, força para guiar e a reflexão de força são ajustados
# na tela Configurações (aegis_config.py) e chegam ao worker em self.cfg.

# Reflexão de força follower -> leader (estimativa do CB3, ruído 15-40 N).
ALFA_REFLEXAO = 0.1         # filtro (menor = mais suave)
# Viés adaptativo da estimativa do follower (valores tirados de uma gravação
# real: o viés muda de 8 a 60 N entre poses e o atrito parado segura ~55 N).
TAU_VIES_MOVENDO = 0.5      # s    viés acompanha a pose enquanto o follower se move
V_ADAPTA_VIES = 0.02        # m/s  acima disso o follower está "se movendo"
TAXA_VIES = 80.0            # N/s  limite de variação do viés (picos não o arrastam)
V_IGNORA_FORCA = 0.12       # m/s  acima disso a estimativa tem picos de até 270 N


# Orientações (Δq4, Δq5, Δq6 em rad) para medir o desvio do sensor do leader.
VARREDURA_PUNHO = [
    (0.0, 0.0, 0.0),
    (0.6, 0.0, 0.0), (-0.6, 0.0, 0.0),
    (0.0, 0.5, 0.0), (0.0, -0.5, 0.0),
    (0.0, 0.0, 1.2), (0.0, 0.0, -1.2),
    (0.4, 0.4, 0.8), (-0.4, -0.4, -0.8),
]


def _perto_singularidade(q, pose_tcp) -> bool:
    """Leader perto de singularidade de punho, cotovelo ou ombro."""
    punho = abs(math.sin(q[4])) < 0.17       # q5 a menos de ~10° de 0/180°
    cotovelo = abs(math.sin(q[2])) < 0.17    # braço quase esticado
    ombro = math.hypot(pose_tcp[0], pose_tcp[1]) < 0.08  # TCP sobre a base
    return punho or cotovelo or ombro
T_CALIBRACAO = 1.5          # s

# Garra: botão na entrada digital 16 do leader (ferramenta).
BOTAO_GARRA = 16
POS_ABERTA_GARRA = 100

# Home
JOINT_HOME = [-1.57, -1.57, -1.57, -1.57, 1.57, 0.0]
VEL_HOME = 1.5    # rad/s
ACEL_HOME = 0.5   # rad/s²


def _robo_responde(ip: str, timeout: float = 2.0) -> bool:
    """Testa a porta RTDE (30004) sem bloquear a interface."""
    try:
        with socket.create_connection((ip, 30004), timeout=timeout):
            return True
    except OSError:
        return False


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
    telemetry_changed = Signal(dict)    # {"UR3e": (q, pose, wrench), "UR5e": (...)}
    forca_changed = Signal(float, float, float)  # t, |F follower| sem viés, força refletida

    def __init__(self, master_ip: str, follower_ip: str, cfg: dict | None = None):
        super().__init__()
        self.cfg = dict(cfg) if cfg is not None else aegis_config.carregar()
        self.modelo_leader = ModeloSensorLeader()
        self._mr = self._fr = None
        self._proxima_telemetria = 0.0
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

    def request_recalibrate(self):
        self._commands.put("recalibrar")

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

    def _emitir_telemetria(self):
        """Envia juntas, TCP e forças dos dois robôs à tela (10 Hz).

        Usa as mesmas conexões RTDE do controle: a tela não abre conexões
        próprias nem trava esperando um robô responder.
        """
        agora = time.monotonic()
        if self._mr is None or agora < self._proxima_telemetria:
            return
        self._proxima_telemetria = agora + 0.1
        try:
            amostras = {
                nome: (tuple(r.getActualQ()), tuple(r.getActualTCPPose()), tuple(r.getActualTCPForce()))
                for nome, r in (("UR3e", self._mr), ("UR5e", self._fr))
            }
        except Exception:
            return
        self.telemetry_changed.emit(amostras)

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

    def _mover_juntas(self, ctrl, q, nome, vel=VEL_HOME, acel=ACEL_HOME):
        """moveJ assíncrono: Parar interrompe o movimento com stopJ."""
        ctrl.moveJ(list(q), vel, acel, True)
        time.sleep(0.1)
        while ctrl.getAsyncOperationProgressEx().isAsyncOperationRunning():
            self._emitir_telemetria()
            if self._stop_requested.is_set():
                ctrl.stopJ(2.0)
                raise _ParadaSolicitada()
            if not ctrl.isProgramRunning():
                raise RuntimeError(f"O script do {nome} parou durante o movimento (protective stop?).")
            time.sleep(0.02)

    def _mover_home(self, ctrl, nome):
        self._status(f"Movendo o {nome} para Home...")
        self._mover_juntas(ctrl, JOINT_HOME, nome)

    def _varrer_sensor_leader(self, mc, mr):
        """Gira o punho do leader por algumas orientações e mede o desvio do sensor.

        Com as amostras paradas, ajusta o modelo F_falsa = a + R·b
        (sensor_leader.py). O leader volta à pose inicial no fim; o follower
        fica parado (não está servoando).
        """
        self._status(
            "Medindo o sensor do leader: o punho do UR3e vai girar um pouco. "
            "Não encoste nos robôs (~15 s)...", "aviso"
        )
        q0 = list(mr.getActualQ())
        usa_q5 = abs(math.sin(q0[4])) > 0.5  # não gira o q5 perto da singularidade
        self.modelo_leader.limpar()
        for d4, d5, d6 in VARREDURA_PUNHO:
            if (d5 and not usa_q5):
                continue
            q = q0[:3] + [q0[3] + d4, q0[4] + d5, q0[5] + d6]
            self._mover_juntas(mc, q, "UR3e (leader)", vel=1.0, acel=1.5)
            time.sleep(0.4)  # deixa assentar
            forcas, t_fim = [], time.monotonic() + 0.3
            while time.monotonic() < t_fim:
                forcas.append(mr.getActualTCPForce()[:3])
                time.sleep(0.008)
            media = [sum(f[i] for f in forcas) / len(forcas) for i in range(3)]
            self.modelo_leader.adicionar(mr.getActualTCPPose(), media)
        self._mover_juntas(mc, q0, "UR3e (leader)", vel=1.0, acel=1.5)
        if self.modelo_leader.ajustar():
            erro = self.modelo_leader.erro_rms
            nivel = "info" if erro < 0.4 else "aviso"
            self._status(
                f"Sensor do leader medido: desvio corrigido com erro de {erro:.2f} N."
                + ("" if erro < 0.4 else " Erro alto: confira o payload do UR3e no pendant."),
                nivel,
            )

    # --- Leader: force mode + reflexão de força (mesma lógica do ur_rtde.py) ---
    def _passo_forca(self, mc, w_lin=(0.0, 0.0, 0.0)):
        mc.forceMode(
            [0, 0, 0, 0, 0, 0],                 # referencial: base
            [1, 1, 1, 1, 1, 1],                 # todos os eixos complacentes
            list(w_lin) + [0.0, 0.0, 0.0],      # força alvo = reflexão (torque zero)
            2,                                  # referencial não transformado
            [VMAX_LIN] * 3 + [VMAX_ROT] * 3,    # limites de velocidade
        )

    def _forca_reflexao(self, fr, f_filt, vies, dt):
        """Força de contato estimada no follower e a força refletida no leader.

        A estimativa do UR5 (CB3) vem das correntes dos motores e erra com a
        pose (viés diferente em cada pose) e com o atrito parado. Por isso o
        viés se adapta: rápido enquanto o follower se move livre, devagar
        quando parado. Contatos curtos passam; um contato mantido some aos
        poucos (tempo "tau_vies_parado" em Configurações). Em movimento
        rápido a estimativa não é confiável e é ignorada.
        """
        bruto = fr.getActualTCPForce()[:3]
        v = math.sqrt(sum(x * x for x in fr.getActualTCPSpeed()[:3]))
        tau = TAU_VIES_MOVENDO if v > V_ADAPTA_VIES else self.cfg["tau_vies_parado"]
        if tau > 0:
            for i in range(3):
                passo = (bruto[i] - vies[i]) * min(dt / tau, 1.0)
                vies[i] += max(-TAXA_VIES * dt, min(TAXA_VIES * dt, passo))
        f = [a - b for a, b in zip(bruto, vies)]
        f_filt = [(1 - ALFA_REFLEXAO) * a + ALFA_REFLEXAO * b for a, b in zip(f_filt, f)]
        norma = math.sqrt(sum(x * x for x in f_filt))
        if v > V_IGNORA_FORCA:
            norma = 0.0
        c = self.cfg
        mag = min(c["k_reflexao"] * max(norma - c["zona_morta_reflexao"], 0.0), c["fmax_reflexao"])
        w = [mag * x / norma for x in f_filt] if mag > 0 else [0.0, 0.0, 0.0]
        return w, f_filt, norma, mag

    def _conectar_garra(self):
        try:
            try:
                from garra_robotiq import Garra
            except ImportError:
                from .garra_robotiq import Garra
            porta = self.cfg["porta_garra"]
            garra = Garra(None if porta == "auto" else porta)
        except Exception as error:
            self._status(f"Garra indisponível ({error}). Seguindo sem garra.", "aviso")
            self._info_set(garra="indisponível")
            return None
        self._status(
            f"Conectando à garra na {garra.porta} (aguarde ~10 s, o USB da câmera reinicia)..."
        )
        try:
            def cancelar():
                self._emitir_telemetria()  # mantém a tela atualizada durante a espera
                return self._stop_requested.is_set()

            garra.conectar(cancelar=cancelar)
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
            # O construtor do ur_rtde segura o Python inteiro (inclusive a
            # tela) até o timeout se o robô não responde. Testa antes com um
            # socket comum, que não trava a interface.
            for nome, ip in (("UR3e (leader)", self.master_ip), ("UR5 (follower)", self.follower_ip)):
                if not _robo_responde(ip):
                    raise RuntimeError(
                        f"O {nome} não responde em {ip}. Confira se ele está ligado, "
                        "com o PolyScope aberto, e se o cabo de rede está conectado."
                    )
                if self._stop_requested.is_set():
                    raise _ParadaSolicitada()
            master_control = RTDEControl(self.master_ip)
            master_receive = RTDEReceive(self.master_ip)
            follower_control = RTDEControl(self.follower_ip)
            follower_receive = RTDEReceive(self.follower_ip)
            self._mr, self._fr = master_receive, follower_receive
            self._emitir_telemetria()
            self._status("RTDE conectado aos dois robôs.")
            self._info_set(leader="travado", reflexao="inativa" if self.cfg["reflexao"] else "desligada")

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
            proximo_grafico = 0.0
            t_ultimo_ciclo = None
            leader_parado_desde = None
            ultimo_zero_lider = 0.0      # última amostra parada do sensor do leader
            ultimo_ajuste_modelo = 0.0
            ultimo_aviso_sing = 0.0

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
                self._emitir_telemetria()
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
                        self._varrer_sensor_leader(master_control, master_receive)
                        master_control.forceModeSetDamping(self.cfg["amortecimento"])
                        master_control.forceModeSetGainScaling(self.cfg["ganho_forca"])
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

                if (command == "recalibrar" and MODO_GUIA == "forca"
                        and self._tracking_ready.is_set() and not self._pause_requested.is_set()):
                    # Zera o sensor do leader e mede de novo o viés do follower,
                    # sem precisar de um Home completo.
                    self._status("Recalibrando: não encoste nos robôs...", "aviso")
                    if servo_active:
                        follower_control.servoStop()
                        servo_active = False
                    leader_parado()
                    time.sleep(0.5)
                    master_control.zeroFtSensor()
                    time.sleep(0.2)
                    self._varrer_sensor_leader(master_control, master_receive)
                    reiniciar_calibracao()

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
                    if self.cfg["reflexao"] and vies_follower is None:
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
                        # Durante a calibração o leader fica em teach mode (parado):
                        # em force mode o desvio do sensor dele o faria andar sozinho.
                        if not teach_mode:
                            if force_mode:
                                master_control.forceModeStop()
                                force_mode = False
                            master_control.teachMode()
                            teach_mode = True
                            self._info_set(leader="teach")
                    else:
                        agora = time.monotonic()
                        dt_ciclo = min(agora - t_ultimo_ciclo, 0.1) if t_ultimo_ciclo else dt
                        t_ultimo_ciclo = agora
                        if self.cfg["reflexao"]:
                            w_ref, f_filt, f_mag, mag_ref = self._forca_reflexao(
                                follower_receive, f_filt, vies_follower, dt_ciclo
                            )
                        else:
                            w_ref, mag_ref = (0.0, 0.0, 0.0), 0.0

                        # Força da mão no leader, sem o desvio do sensor (que muda
                        # com a orientação; modelo medido no Home).
                        pose_lider = master_receive.getActualTCPPose()
                        f_bruta_lider = master_receive.getActualTCPForce()[:3]
                        f_corr_lider = self.modelo_leader.corrigir(pose_lider, f_bruta_lider)
                        f_lider = float(math.sqrt(sum(x * x for x in f_corr_lider)))
                        # Histerese: entra em force mode acima de "força para guiar" e
                        # só sai abaixo de "força para soltar". Sem a mão, o leader
                        # fica em teach mode, que não anda sozinho.
                        f_entra = self.cfg["f_entra_force"]
                        f_sai = min(self.cfg["f_sai_force"], 0.8 * f_entra)
                        mao = f_lider > (f_sai if force_mode else f_entra)

                        # Perto de singularidade o force mode pode disparar o
                        # leader; nesse caso fica em teach mode (move só à mão).
                        if mao and _perto_singularidade(joint_master, pose_lider):
                            mao = False
                            if agora - ultimo_aviso_sing > 3.0:
                                ultimo_aviso_sing = agora
                                self._status(
                                    "Leader perto de uma singularidade: força desligada. "
                                    "Afaste-o à mão (teach mode).", "aviso"
                                )

                        if mao:
                            if teach_mode:
                                master_control.endTeachMode()
                                teach_mode = False
                            self._passo_forca(master_control, w_ref)
                            force_mode = True
                            leader_parado_desde = None
                            self._info_set(leader="força")
                        else:
                            if not teach_mode:
                                if force_mode:
                                    master_control.forceModeStop()
                                    force_mode = False
                                master_control.teachMode()
                                teach_mode = True
                                leader_parado_desde = None
                                self._info_set(leader="teach")
                            # Leader parado e sem mão: a leitura é só o desvio do
                            # sensor nessa orientação. Vira amostra do modelo, que
                            # assim acompanha poses novas e o aquecimento do sensor.
                            v_lider = math.sqrt(
                                sum(x * x for x in master_receive.getActualTCPSpeed()[:3])
                            )
                            if v_lider < 0.003:
                                if leader_parado_desde is None:
                                    leader_parado_desde = agora
                                elif (agora - leader_parado_desde > 0.5
                                      and agora - ultimo_zero_lider > 0.5
                                      and f_lider < 2.0):
                                    self.modelo_leader.adicionar(pose_lider, f_bruta_lider, fixa=False)
                                    ultimo_zero_lider = agora
                                    if agora - ultimo_ajuste_modelo > 1.0:
                                        self.modelo_leader.ajustar()
                                        ultimo_ajuste_modelo = agora
                            else:
                                leader_parado_desde = None

                        refletindo = mao and mag_ref > 0
                        if self.cfg["reflexao"]:
                            self._info_set(reflexao="refletindo" if refletindo else "inativa")
                            if agora >= proximo_grafico:  # 20 Hz para o gráfico de força
                                proximo_grafico = agora + 0.05
                                self.forca_changed.emit(agora, f_mag, mag_ref if mao else 0.0)

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
            self._mr = self._fr = None
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
    telemetry_changed = Signal(dict)
    forca_changed = Signal(float, float, float)

    def __init__(self, master_ip: str, follower_ip: str):
        super().__init__()
        self.master_ip = master_ip
        self.follower_ip = follower_ip
        self.cfg: dict | None = None
        self.worker: _JoshuaRTDEWorker | None = None

    def ativo(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def iniciar(self):
        if self.ativo():
            return
        self.worker = _JoshuaRTDEWorker(self.master_ip, self.follower_ip, self.cfg)
        self.worker.status_changed.connect(self.status_changed)
        self.worker.state_changed.connect(self.state_changed)
        self.worker.info_changed.connect(self.info_changed)
        self.worker.telemetry_changed.connect(self.telemetry_changed)
        self.worker.forca_changed.connect(self.forca_changed)
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

    def recalibrar(self):
        if self.ativo():
            self.worker.request_recalibrate()

    def parar(self):
        """Não bloqueia a interface: o worker encerra e emite o estado final."""
        if self.ativo():
            self.state_changed.emit("parando")
            self.worker.request_stop()

    def encerrar(self):
        if self.ativo():
            self.worker.request_stop()
            self.worker.wait()


class _TelemetriaDoControle:
    """Fonte de telemetria da tela alimentada pelo worker de controle."""

    def __init__(self):
        self.amostras = {}

    def atualizar(self, amostras):
        self.amostras = {
            nome: RobotTelemetry(q, pose, wrench) for nome, (q, pose, wrench) in amostras.items()
        }

    def read(self):
        return self.amostras

    def close(self):
        pass


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
        self.controlador.telemetry_changed.connect(self._receber_telemetria)
        self.controlador.forca_changed.connect(self.add_force_sample)
        self.recalibrar_solicitado.connect(self.controlador.recalibrar)
        self.controlador.state_changed.connect(self._ao_mudar_estado)
        self._telemetria = _TelemetriaDoControle()

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
        # Usa os parâmetros salvos; os IPs digitados também ficam salvos.
        cfg = dict(self.config)
        cfg["ip_leader"] = self.controlador.master_ip
        cfg["ip_follower"] = self.controlador.follower_ip
        if (cfg["ip_leader"], cfg["ip_follower"]) != (self.config["ip_leader"], self.config["ip_follower"]):
            try:
                self.config = aegis_config.salvar(cfg)
            except OSError:
                pass
        self.controlador.cfg = cfg
        self.add_log(
            "Parâmetros: amortecimento {amortecimento:.3f}, ganho {ganho_forca:.2f}, "
            "guiar acima de {f_entra_force:.1f} N, reflexão {r} (ganho {k_reflexao:.2f}, "
            "zona morta {zona_morta_reflexao:.0f} N, máx {fmax_reflexao:.1f} N), garra {porta_garra}.".format(
                r="ligada" if cfg["reflexao"] else "desligada", **cfg)
        )
        self.telemetry_status.setText("Conectando aos robôs...")
        self.iniciar_solicitado.emit()

    def _receber_telemetria(self, amostras):
        """A telemetria vem do worker de controle (sem conexões extras)."""
        self._telemetria.atualizar(amostras)
        if self.telemetry_source is not self._telemetria:
            self.set_telemetry_source(self._telemetria)
            self.telemetry_status.setText("Conectado • telemetria real, somente leitura")
            self._set_level(self.telemetry_status, "info")
            for source_label in self.source_labels:
                source_label.setText("RTDE • leitura real")

    def _ao_mudar_estado(self, estado):
        if estado in ("desconectado", "erro"):
            self.disconnect_telemetry("Sem leitura • pressione Iniciar")

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
