"""Garra Robotiq via Modbus RTU, pela serial USB da Robotiq Wrist Camera.

Mesma lógica do ur_rtde.py: espera a comunicação ficar estável (a câmera
reinicia o USB alguns segundos depois da porta abrir), ativa a garra e repete
comandos quando a resposta chega corrompida (o comando é idempotente).
"""

from __future__ import annotations

import time

import minimalmodbus
import serial
from serial.tools import list_ports

# USB serial da Robotiq Wrist Camera (VID 16D0, PID 0BC3).
VID_CAMERA = 0x16D0
PID_CAMERA = 0x0BC3
PORTA_PADRAO = "COM4"

POS_ABERTA = 100
POS_FECHADA = 250


def detectar_porta() -> str:
    """Acha a COM da câmera do punho; usa PORTA_PADRAO se não achar."""
    for p in list_ports.comports():
        if p.vid == VID_CAMERA and p.pid == PID_CAMERA:
            return p.device
    return PORTA_PADRAO


class Garra:
    def __init__(self, porta: str | None = None, escravo: int = 9):
        self.porta = porta or detectar_porta()
        self.inst = minimalmodbus.Instrument(self.porta, escravo, mode=minimalmodbus.MODE_RTU)
        s = self.inst.serial
        s.baudrate = 115200
        s.bytesize = 8
        s.parity = serial.PARITY_NONE
        s.stopbits = 1
        s.timeout = 0.5
        s.write_timeout = 0.5
        self.inst.clear_buffers_before_each_transaction = True
        self.fechada: bool | None = None

    def ler_estado(self) -> dict:
        r = self.inst.read_registers(2000, 3, functioncode=4)
        status = r[0] >> 8
        return {
            "ativa": bool(status & 1),
            "ativacao": (status >> 4) & 3,
            "movimento": (status >> 6) & 3,
            "falha": (r[1] >> 8) & 0x0F,
            "pedido": r[1] & 0xFF,
            "posicao": r[2] >> 8,
        }

    def conectar(self, timeout: float = 30.0, estavel: float = 8.0, cancelar=None):
        """Lê até a comunicação ficar estável por `estavel` s."""
        inicio = time.monotonic()
        ok_desde = None
        while time.monotonic() - inicio < timeout:
            if cancelar is not None and cancelar():
                raise RuntimeError("Conexão da garra cancelada")
            try:
                if not self.inst.serial.is_open:
                    self.inst.serial.open()
                    time.sleep(0.3)
                self.ler_estado()
                if ok_desde is None:
                    ok_desde = time.monotonic()
                elif time.monotonic() - ok_desde >= estavel:
                    return
            except (serial.SerialException, minimalmodbus.ModbusException, OSError):
                ok_desde = None
                try:
                    self.inst.serial.close()
                except Exception:
                    pass
                time.sleep(0.5)
            time.sleep(0.05)
        raise RuntimeError(f"Garra não respondeu de forma estável na {self.porta}")

    def ativar(self):
        e = self.ler_estado()
        if e["ativa"] and e["ativacao"] == 3:
            return
        self.inst.write_registers(1000, [0x0000, 0, 0])
        time.sleep(0.1)
        self.inst.write_registers(1000, [0x0100, 0, 0])
        # A ativação leva alguns segundos; espera terminar.
        fim = time.monotonic() + 10
        while time.monotonic() < fim:
            try:
                e = self.ler_estado()
                if e["ativa"] and e["ativacao"] == 3:
                    return
            except (minimalmodbus.ModbusException, serial.SerialException, OSError):
                pass
            time.sleep(0.1)

    def mover(self, posicao: int, velocidade: int = 50, forca: int = 30) -> bool:
        if not all(0 <= v <= 255 for v in (posicao, velocidade, forca)):
            raise ValueError("Os valores devem estar entre 0 e 255.")
        for tentativa in range(3):
            try:
                self.inst.write_registers(1000, [0x0900, posicao, (velocidade << 8) | forca])
                return True
            except (minimalmodbus.ModbusException, serial.SerialException, OSError):
                time.sleep(0.03)
        return False

    def atualizar_botao(self, apertado: bool) -> str | None:
        """Fecha com o botão apertado e abre solto; só envia na mudança.

        Retorna uma mensagem quando algo aconteceu, senão None.
        """
        if apertado == self.fechada:
            return None
        self.fechada = apertado
        ok = self.mover(POS_FECHADA if apertado else POS_ABERTA)
        acao = "fechando" if apertado else "abrindo"
        return f"Garra {acao}." if ok else f"Aviso: garra não confirmou o comando ({acao})."

    def fechar_porta(self):
        try:
            self.inst.serial.close()
        except Exception:
            pass
