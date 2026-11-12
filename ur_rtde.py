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


def esperar(condicao, timeout=0.10):
    inicio = time.monotonic()

    while time.monotonic() - inicio < timeout:
        estado = 1
    estado = ler_estado()
    return estado

def atualizar_botao(apertado):
    posicao = 250 if apertado else 100
    return posicao

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
        garra.write_registers(1000, [0x0900, posicao, (velocidade << 8) | forca])
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

ativar()
mover(100,0)
time.sleep(0.1)

try:

    while not parar.is_set():
        t_start = rtde_follow_c.initPeriod()

        aceleracao_master = rtde_master_r.getActualToolAccelerometer()
        aceleracao_follow = rtde_follow_r.getActualToolAccelerometer()

        pose_tcp_m = rtde_master_r.getActualTCPPose()
        pose_tcp_f = rtde_follow_r.getActualTCPPose()

        R_base_tcp_m = Rotation.from_rotvec(pose_tcp_m[3:]).as_matrix()
        R_base_tcp_f = Rotation.from_rotvec(pose_tcp_f[3:]).as_matrix()

        a_base_m = R_base_tcp_m @ aceleracao_master
        a_base_f = R_base_tcp_f @ aceleracao_follow

        a_base_f[2] = a_base_f[2] - 1.9
        
        erro = [abs(a_f - a_m) for a_f,a_m in zip(a_base_f,a_base_m)]

        posicao = atualizar_botao(rtde_master_r.getDigitalInState(16))

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
            
        rtde_follow_c.servoJ(joint_master, 0, 0, dt, lookahead_time, gain)
        
        # else:
        #     print("Entrou no if")
        
        rtde_follow_c.waitPeriod(t_start)

finally:
    garra.serial.close()

    rtde_follow_c.servoStop()
    rtde_master_c.endTeachMode()

    rtde_follow_c.stopScript()
    rtde_master_c.stopScript()

    rtde_master_c.disconnect()
    rtde_follow_c.disconnect()

print("Programa encerrado")