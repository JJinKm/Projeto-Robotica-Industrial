from rtde_receive import RTDEReceiveInterface as RTDEReceive
from rtde_control import RTDEControlInterface as RTDEControl
import time
import threading
import math
from scipy.spatial.transform import Rotation
import time
import serial
import minimalmodbus

garra = minimalmodbus.Instrument(
    "COM3", 9, mode=minimalmodbus.MODE_RTU
)

garra.serial.baudrate = 115200
garra.serial.bytesize = 8
garra.serial.parity = serial.PARITY_NONE
garra.serial.stopbits = 1
garra.serial.timeout = 0.5
garra.serial.write_timeout = 0.5
garra.clear_buffers_before_each_transaction = True


def ler_estado():
    # FC04: lê os três registradores de estado
    r = garra.read_registers(2000, 3, functioncode=4)
    status = r[0] >> 8

    return {
        "ativa": bool(status & 1),
        "ativacao": (status >> 4) & 3,
        "movimento": (status >> 6) & 3,
        "falha": (r[1] >> 8) & 0x0F,
        "pedido": r[1] & 0xFF,
        "posicao": r[2] >> 8,
    }


def conectar_garra(timeout=30, estavel=8.0):
    # A garra fala pela COM da Wrist Camera, que às vezes reinicia o USB
    # alguns segundos depois da porta ser aberta. Fica lendo (e reabrindo a
    # porta se ela sumir) até a comunicação ficar estável por `estavel` s.
    inicio = time.monotonic()
    ok_desde = None
    while time.monotonic() - inicio < timeout:
        try:
            if not garra.serial.is_open:
                garra.serial.open()
                time.sleep(0.3)
            ler_estado()
            if ok_desde is None:
                ok_desde = time.monotonic()
            elif time.monotonic() - ok_desde >= estavel:
                return
        except (serial.SerialException, minimalmodbus.ModbusException, OSError):
            ok_desde = None
            try:
                garra.serial.close()
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(0.05)
    raise RuntimeError("Garra não respondeu de forma estável na porta serial")


def esperar(condicao, timeout=0.10):
    inicio = time.monotonic()

    while time.monotonic() - inicio < timeout:
        estado = 1
    estado = ler_estado()
    return estado

def atualizar_botao(apertado):
    global garra_moving
    global garra_close
    posicao = 250 if apertado else 100
    if posicao == 250 and garra_close == 0:
        garra_moving = mover(posicao,garra_moving)
        if garra_close == 0:
            garra_moving = 0
        garra_close = 1
    elif posicao == 100 and garra_close == 1:
        garra_moving = mover(posicao,garra_moving)
        if garra_close == 1:
            garra_moving = 0
        garra_close = 0


def ativar():
    estado = ler_estado()

    if estado["ativa"] and estado["ativacao"] == 3:
        return

    # Reset e confirmação
    garra.write_registers(1000, [0x0000, 0, 0])
    esperar(lambda e: not e["ativa"] and e["ativacao"] == 0)

    # rACT = 1
    garra.write_registers(1000, [0x0100, 0, 0])
    esperar(lambda e: e["ativa"] and e["ativacao"] == 3)


def mover(posicao, garra_moving, velocidade=50, forca=30):
    if not all(0 <= v <= 255 for v in (posicao, velocidade, forca)):
        raise ValueError("Os valores devem estar entre 0 e 255.")

    # rACT=1, rGTO=1; posição; velocidade e força
    if garra_moving == 0:
        # O link serial passa pela câmera do punho e às vezes devolve a resposta
        # corrompida (InvalidResponseError / checksum), principalmente com
        # comandos em sequência rápida. O comando é idempotente, então repete.
        for tentativa in range(3):
            try:
                garra.write_registers(1000, [0x0900, posicao, (velocidade << 8) | forca])
                break
            except (minimalmodbus.ModbusException, serial.SerialException, OSError) as e:
                time.sleep(0.03)
                if tentativa == 2:
                    print(f"Aviso: garra não confirmou o comando ({type(e).__name__}); seguindo.")
        return 1

    # time.sleep(0.1)
    # return esperar(
    #     lambda e: e["pedido"] == posicao and e["movimento"] != 0
    # )



flags = RTDEControl.FLAG_UPLOAD_SCRIPT | RTDEControl.FLAG_VERBOSE

rtde_master_c = RTDEControl("10.104.11.99")
rtde_master_r = RTDEReceive("10.104.11.99")

rtde_follow_c = RTDEControl("10.104.11.71")
rtde_follow_r = RTDEReceive("10.104.11.71")

parar = threading.Event()

def esperar_enter():
   input("Pressione ENTER para encerrar o script de controle...\n")
   parar.set()

threading.Thread(target=esperar_enter,daemon=True).start()


joint_home = [-1.57, -1.57, -1.57, -1.57, 1.57,0]

rtde_master_c.moveJ(joint_home,1.5,0.5)
rtde_follow_c.moveJ(joint_home,1.5,0.5)
print("Robôs em posição inicial")

# --- Modo de guiar o leader ---------------------------------------------
# "forca": force mode nativo do UR no leader, com força alvo zero em todos os
#          eixos. O controlador move o robô na direção da força que você aplica
#          na ferramenta (sensor F/T do UR3e) e NÃO trata isso como colisão.
#          Só sente força aplicada DEPOIS do sensor (ferramenta/flange).
# "teach": freedrive normal do UR (comportamento antigo).
MODO_GUIA = "forca"

AMORTECIMENTO = 0.015  # 0..1  maior = para mais rápido ao soltar; menor = "desliza" (inércia) 0.02
GANHO_FORCA = 2.0     # 0..2  maior = responde mais rápido ao empurrão (>1 pode oscilar) 2.0
VMAX_LIN = 0.25       # m/s   velocidade máx. nos eixos lineares 0.25
VMAX_ROT = 0.8        # rad/s velocidade máx. nos eixos de rotação
DEBUG_FORCA = True    # imprime força lida 2x/s

# --- Reflexão de força (follower -> leader) -------------------------------
# O UR5 (CB3) não tem sensor de força, mas estima a força no TCP pelas
# correntes dos motores (getActualTCPForce). Essa estimativa é ruidosa
# (~15-40 N parado), mas um contato firme passa de 100 N. O que passar da
# zona morta é aplicado no leader, NA MESMA DIREÇÃO em que o ambiente empurra
# o follower (ex.: mesa empurra o follower p/ cima -> leader empurra a mão p/
# cima). Sinal validado: empurrar o follower p/ baixo deu F_z negativo.
REFLEXAO = True
K_REFLEXAO = 0.1           # N no leader por N no follower
ZONA_MORTA_REFLEXAO = 30.0 # N   abaixo disso é ruído da estimativa do CB3
FMAX_REFLEXAO = 10.0       # N   força máxima aplicada no leader
ALFA_REFLEXAO = 0.1        # filtro (0..1, menor = mais suave, mais atraso)
T_CALIBRACAO = 1.5         # s   tempo p/ medir o viés com o follower servoando


def forca_reflexao(f_filt, vies):
    f = [a - b for a, b in zip(rtde_follow_r.getActualTCPForce()[:3], vies)]
    f_filt = [(1 - ALFA_REFLEXAO) * a + ALFA_REFLEXAO * b for a, b in zip(f_filt, f)]
    norma = math.sqrt(sum(x * x for x in f_filt))
    mag = min(K_REFLEXAO * max(norma - ZONA_MORTA_REFLEXAO, 0.0), FMAX_REFLEXAO)
    w = [mag * x / norma for x in f_filt] if mag > 0 else [0.0, 0.0, 0.0]
    return w, f_filt, norma


def passo_forca(w_lin=(0.0, 0.0, 0.0), f_follower=0.0):
    ok = rtde_master_c.forceMode(
        [0, 0, 0, 0, 0, 0],                 # referencial: base
        [1, 1, 1, 1, 1, 1],                 # todos os eixos complacentes
        list(w_lin) + [0.0, 0.0, 0.0],      # força alvo = reflexão (torque zero)
        2,                                  # referencial não transformado
        [VMAX_LIN] * 3 + [VMAX_ROT] * 3,    # limites de velocidade
    )
    global ultimo_debug
    if DEBUG_FORCA and time.monotonic() - ultimo_debug > 0.5:
        ultimo_debug = time.monotonic()
        f = rtde_master_r.getActualTCPForce()
        print("F_leader=[" + " ".join(f"{x:6.1f}" for x in f[:3]) + "]  "
              f"|F_follower|={f_follower:6.1f} N  "
              "F_reflexao=[" + " ".join(f"{x:5.1f}" for x in w_lin) + f"]  ok={ok}")


ultimo_debug = 0.0
f_filt = [0.0, 0.0, 0.0]
vies_follower = None
amostras_vies = []
t_inicio_loop = None


if MODO_GUIA == "teach":
    rtde_master_c.teachMode()

m = 1 # Massa da garra [kg]

dt = 0.008
lookahead_time = 0.1
gain = 300

amax = 0.5
vmax = 1.5
vel_anterior = 0.0

joint_follow = rtde_follow_r.getActualQ()

estado = {}
garra_close = 0
garra_moving = 0
f_mag = 0

teachmode_flag = 0
F_ENTRA_FORCE = 1.1   # N  acima disso o leader sai do teach mode e vai p/ force mode
F_SAI_FORCE = 0.5     # N  abaixo disso o leader volta p/ teach mode

conectar_garra()
ativar()
mover(100,0)
time.sleep(0.1)

if MODO_GUIA == "forca":
    # Zera o sensor com o leader parado e sem ninguém encostando
    print("Zerando sensor de força do leader, não encoste no robô...")
    time.sleep(0.5)
    rtde_master_c.zeroFtSensor()
    time.sleep(0.2)
    rtde_master_c.forceModeSetDamping(AMORTECIMENTO)
    rtde_master_c.forceModeSetGainScaling(GANHO_FORCA)
    print("Leader em force mode: pode guiar pela ferramenta")
    if REFLEXAO:
        print(f"Calibrando força do follower por {T_CALIBRACAO} s: "
              "não encoste no follower...")

try:

    while not parar.is_set():
        t_start = rtde_follow_c.initPeriod()

        # aceleracao_master = rtde_master_r.getActualToolAccelerometer()
        # aceleracao_follow = rtde_follow_r.getActualToolAccelerometer()

        # pose_tcp_m = rtde_master_r.getActualTCPPose()
        # pose_tcp_f = rtde_follow_r.getActualTCPPose()

        # R_base_tcp_m = Rotation.from_rotvec(pose_tcp_m[3:]).as_matrix()
        # R_base_tcp_f = Rotation.from_rotvec(pose_tcp_f[3:]).as_matrix()

        # a_base_m = R_base_tcp_m @ aceleracao_master
        # a_base_f = R_base_tcp_f @ aceleracao_follow

        # a_base_f[2] = a_base_f[2] - 1.9
        
        # erro = [abs(a_f - a_m) for a_f,a_m in zip(a_base_f,a_base_m)]

        posicao = atualizar_botao(rtde_master_r.getDigitalInState(16))

        # if posicao == 250 and garra_close == 0:
        #     garra_moving = mover(posicao,garra_moving)
        #     if garra_close == 0:
        #         garra_moving = 0
        #     garra_close = 1
        # elif posicao == 100 and garra_close == 1:
        #     garra_moving = mover(posicao,garra_moving)
        #     if garra_close == 1:
        #         garra_moving = 0
        #     garra_close = 0


        # if (abs(a_base_m[0]) > 0.9 or abs(a_base_m[1]) > 0.9 or abs(a_base_m[2]) > 10):
        #     print("Garra em movimento")
        #     print(a_base_f)
        #     print(a_base_m)
        #     print(erro)
        # elif (e < 0.9 for e in erro):
        #     print("Garra parada")
        #     print(erro)

        joint_follow = rtde_follow_r.getActualQ()
        joint_master = rtde_master_r.getActualQ()

        # if any(e < 0.5 for e in erro):
            
        if MODO_GUIA == "forca":
            if REFLEXAO and vies_follower is None:
                # Mede o viés da estimativa com o follower já servoando
                if t_inicio_loop is None:
                    t_inicio_loop = time.monotonic()
                amostras_vies.append(rtde_follow_r.getActualTCPForce()[:3])
                if time.monotonic() - t_inicio_loop >= T_CALIBRACAO:
                    n = len(amostras_vies)
                    vies_follower = [sum(a[i] for a in amostras_vies) / n for i in range(3)]
                    print("Viés do follower: [" +
                          " ".join(f"{x:6.1f}" for x in vies_follower) +
                          "] N. Reflexão de força ATIVA.")
                passo_forca()
            elif REFLEXAO:
                w_ref, f_filt, f_mag = forca_reflexao(f_filt, vies_follower)
                f_lider = math.sqrt(sum(x*x for x in rtde_master_r.getActualTCPForce()[:3]))
                # Histerese: entra em force mode acima de F_ENTRA_FORCE e só volta
                # ao teach mode abaixo de F_SAI_FORCE, evitando trocar de modo
                # várias vezes por segundo quando a força oscila perto do limiar.
                w_lider = math.sqrt(sum(x*x for x in w_ref))
                
                if f_lider > F_ENTRA_FORCE:
                    if teachmode_flag:
                        rtde_master_c.endTeachMode()
                        teachmode_flag = 0
                    passo_forca(w_ref, f_mag)
                    print("Primeiro if força no lider: {0}".format(f_lider))
                elif f_lider < F_SAI_FORCE:
                    if not teachmode_flag:
                        rtde_master_c.forceModeStop()
                        rtde_master_c.teachMode()
                        teachmode_flag = 1
                    print("Segundo if força no lider: {0}".format(f_lider))
                else:
                    if not teachmode_flag:
                        rtde_master_c.forceModeStop()
                        rtde_master_c.teachMode()
                        teachmode_flag = 1
            else:
                passo_forca()

        # Se o script de algum robô morreu (ex.: protective stop), para tudo
        if not (rtde_master_c.isProgramRunning() and rtde_follow_c.isProgramRunning()):
            garra.serial.close()
            print("Script de controle parou em um dos robôs "
                  "(protective stop?). Encerrando.")
            break


        rtde_follow_c.servoJ(joint_master, 0, 0, dt, lookahead_time, gain)
        
        # else:
        #     print("Entrou no if")
        
        rtde_follow_c.waitPeriod(t_start)

finally:
    garra.serial.close()

    rtde_follow_c.servoStop()
    if MODO_GUIA == "forca":
        rtde_master_c.forceModeStop()
        rtde_master_c.endTeachMode()

    else:
        rtde_master_c.endTeachMode()

    rtde_follow_c.stopScript()
    rtde_master_c.stopScript()

    rtde_master_c.disconnect()
    rtde_follow_c.disconnect()

print("Programa encerrado")