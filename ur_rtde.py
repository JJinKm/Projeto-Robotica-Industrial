from rtde_receive import RTDEReceiveInterface as RTDEReceive
from rtde_control import RTDEControlInterface as RTDEControl
import time
import threading
import math
from scipy.spatial.transform import Rotation


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

        if any(e < 0.5 for e in erro):
            rtde_follow_c.servoJ(joint_master, 0, 0, dt, lookahead_time, gain)
        else:
            print("Entrou no if")
        
        rtde_follow_c.waitPeriod(t_start)

finally:
    rtde_follow_c.servoStop()
    rtde_master_c.endTeachMode()

    rtde_follow_c.stopScript()
    rtde_master_c.stopScript()

    rtde_master_c.disconnect()
    rtde_follow_c.disconnect()

print("Programa encerrado")


# Get the current TCP pose [x, y, z, rx, ry, rz]
# tcp_pose = rtde_r_.getActualTCPPose()
# print("TCP position (m):            ", tcp_pose[:3])
# print("TCP orientation (axis-angle):", tcp_pose[3:])

# rtde_io_.setStandardDigitalOut(0,True)

# if rtde_r_.getDigitalOutState(16):
#     print("Tool digital out (16) is HIGH")
# else:
#     print("Tool digital out (16) is LOW")