import rtde_control
print("RTDE Control importado...")
import rtde_receive
print("RTDE Receive importado...")
import time
print("time importado...")

IP = "10.104.11.77"  # IP do robô
IP2 = "10.104.11.77"
print("IP setado em: 10.104.11.77")

cont_ur3 = rtde_control.RTDEControlInterface(IP)
print("Conexão com UR3e estabelecida!")

rec_ur3 = rtde_receive.RTDEReceiveInterface(IP)
print("Recebendo dados do UR3e!")

rec_ur5 = rtde_receive.RTDEReceiveInterface(IP2)
print("Recebendo dados do UR5e!")

forca_atual = rec_ur5.getActualTCPForce()
print("Força TCP UR5e: ", forca_atual)

lista_forca = [2 if f > 15 else -2 if f < -15 else 0 for f in forca_atual]
print("Lista de força ajustada: ", lista_forca)

try:

    cont_ur3.forceModeSetDamping(0.005)      # Desaceleração do robô
    cont_ur3.forceModeSetGainScaling(1.0)   # Ganho de força

    while True:
        
        pose_tcp = rec_ur3.getActualTCPPose()
                        
        forca_atual = rec_ur5.getActualTCPForce()
        lista_forca = [2 if f > 15 else -2 if f < -15 else 0 for f in forca_atual]
        print("Lista de força ajustada: ", lista_forca)
        cont_ur3.forceMode(
            pose_tcp,                 # Referencial: tcp
            [1, 1, 1, 1, 1, 1],       # Eixos complacentes
            [0,0,0,0,0,0],              # Força nula
            2,                        # Referencial inalterado
            [0.5, 0.5, 0.5, 0.2, 0.2, 0.2]
        )

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Interrupção via terminal!")

finally:
    cont_ur3.forceModeStop()
    print("Force Mode encerrado!")
    cont_ur3.disconnect()
    print("Control desconectado!")
    rec_ur3.disconnect()
    print("Receive desconectado!")
    rec_ur5.disconnect()
    print("Receive UR5e desconectado!")
