"""Leitura de telemetria RTDE sem comandos de movimento.

Este módulo não abre conexões ao ser importado ou instanciado. A conexão só
acontece quando connect() é chamado explicitamente. A interface ELO continua
usando dados simulados por padrão.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RobotTelemetry:
    """Amostra em unidades nativas do ur_rtde: rad, m, rad, N e Nm."""

    joint_positions_rad: tuple[float, ...]
    tcp_pose_m_rad: tuple[float, ...]
    tcp_wrench_n_nm: tuple[float, ...]


class RTDETelemetrySource:
    """Adaptador somente de leitura para UR3e e UR5e.

    Passe os endereços ao criar a instância, mas chame connect() apenas quando
    houver autorização para habilitar comunicação física. Não usa RTDEControl.
    """

    def __init__(self, robot_addresses, receiver_factory=None):
        self.robot_addresses = dict(robot_addresses)
        required_robots = {"UR3e", "UR5e"}
        if set(self.robot_addresses) != required_robots:
            raise ValueError("Informe os endereços de UR3e e UR5e.")
        self.receiver_factory = receiver_factory
        self._receivers = {}

    def connect(self):
        if self._receivers:
            return
        if self.receiver_factory is None:
            from rtde_receive import RTDEReceiveInterface

            receiver_factory = RTDEReceiveInterface
        else:
            receiver_factory = self.receiver_factory

        opened = {}
        try:
            for robot_name, address in self.robot_addresses.items():
                opened[robot_name] = receiver_factory(address)
        except Exception:
            for receiver in opened.values():
                try:
                    receiver.disconnect()
                except Exception:
                    pass
            raise
        self._receivers = opened

    def read(self):
        if not self._receivers:
            raise RuntimeError("Chame connect() antes de ler a telemetria RTDE.")

        samples = {}
        for robot_name, receiver in self._receivers.items():
            joints = tuple(receiver.getActualQ())
            tcp_pose = tuple(receiver.getActualTCPPose())
            tcp_wrench = tuple(receiver.getActualTCPForce())
            if not all(len(values) == 6 for values in (joints, tcp_pose, tcp_wrench)):
                raise ValueError(f"A amostra RTDE de {robot_name} não contém seis valores por sinal.")
            samples[robot_name] = RobotTelemetry(joints, tcp_pose, tcp_wrench)
        return samples

    def close(self):
        receivers, self._receivers = self._receivers, {}
        for receiver in receivers.values():
            try:
                receiver.disconnect()
            except Exception:
                pass
