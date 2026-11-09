from rtde_receive import RTDEReceiveInterface as RTDEReceive
from rtde_control import RTDEControlInterface as RTDEControl
import time
import threading
import math

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

# rtde_master_c.teachMode()

joint_home = [-1.57, -1.57, -1.57, -1.57, 1.57,0]

rtde_master_c.moveJ(joint_home,1.5,0.5)
rtde_follow_c.moveJ(joint_home,1.5,0.5)
print("Robôs em posição inicial")
rtde_master_c.teachMode()

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

        joint_follow = rtde_follow_r.getActualQ()
        joint_master = rtde_master_r.getActualQ()

        rtde_follow_c.servoJ(joint_master, 0, 0, dt, lookahead_time, gain)
        
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