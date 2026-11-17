"""Modelos 3D UR com malhas visuais oficiais e atualização por juntas RTDE."""

import math
import os
from pathlib import Path

import numpy as np
import pyqtgraph.opengl as gl
import trimesh
from PySide6.QtCore import Qt
from PySide6.QtGui import QMatrix4x4, QVector3D
from PySide6.QtWidgets import QLabel, QStackedLayout, QVBoxLayout, QWidget


LINK_NAMES = ("base", "shoulder", "upperarm", "forearm", "wrist1", "wrist2", "wrist3")
LINK_COLORS = {
    "base": (0.43, 0.48, 0.52, 1.0),
    "shoulder": (0.78, 0.81, 0.84, 1.0),
    "upperarm": (0.84, 0.86, 0.88, 1.0),
    "forearm": (0.81, 0.84, 0.87, 1.0),
    "wrist1": (0.72, 0.76, 0.79, 1.0),
    "wrist2": (0.83, 0.85, 0.87, 1.0),
    "wrist3": (0.67, 0.72, 0.76, 1.0),
}

# (a, d, alpha), segundo a tabela DH idealizada publicada pela Universal Robots.
DH_MODELS = {
    "UR3e": (
        (0.0, 0.15185, math.pi / 2),
        (-0.24355, 0.0, 0.0),
        (-0.2132, 0.0, 0.0),
        (0.0, 0.13105, math.pi / 2),
        (0.0, 0.08535, -math.pi / 2),
        (0.0, 0.0921, 0.0),
    ),
    "UR5e": (
        (0.0, 0.1625, math.pi / 2),
        (-0.425, 0.0, 0.0),
        (-0.3922, 0.0, 0.0),
        (0.0, 0.1333, math.pi / 2),
        (0.0, 0.0997, -math.pi / 2),
        (0.0, 0.0996, 0.0),
    ),
}

# Transformações dos arquivos visuais no URDF oficial (xyz em metros; rpy em radianos).
VISUAL_ORIGINS = {
    "UR3e": (
        ((0, 0, 0), (0, 0, math.pi)),
        ((0, 0, 0), (0, 0, math.pi)),
        ((0, 0, 0.12), (math.pi / 2, 0, -math.pi / 2)),
        ((0, 0, 0.027), (math.pi / 2, 0, -math.pi / 2)),
        ((0, 0, -0.104), (math.pi / 2, 0, 0)),
        ((0, 0, -0.08535), (0, 0, 0)),
        ((0, 0, -0.0921), (math.pi / 2, 0, 0)),
    ),
    "UR5e": (
        ((0, 0, 0), (0, 0, math.pi)),
        ((0, 0, 0), (0, 0, math.pi)),
        ((0, 0, 0.138), (math.pi / 2, 0, -math.pi / 2)),
        ((0, 0, 0.007), (math.pi / 2, 0, -math.pi / 2)),
        ((0, 0, -0.127), (math.pi / 2, 0, 0)),
        ((0, 0, -0.0997), (0, 0, 0)),
        ((0, 0, -0.0989), (math.pi / 2, 0, 0)),
    ),
}


def model_cache_directory():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ELO" / "models"
    return Path.home() / ".local" / "share" / "ELO" / "models"


def _identity():
    return np.eye(4, dtype=float)


def _dh_transform(theta, a, d, alpha):
    ct, st = math.cos(theta), math.sin(theta)
    ca, sa = math.cos(alpha), math.sin(alpha)
    return np.array(
        [
            [ct, -st * ca, st * sa, a * ct],
            [st, ct * ca, -ct * sa, a * st],
            [0.0, sa, ca, d],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def _origin_transform(xyz, rpy):
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rotation = np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=float,
    )
    transform = _identity()
    transform[:3, :3] = rotation
    transform[:3, 3] = xyz
    return transform


def link_transforms(robot_name, joint_angles_deg):
    """Calcula os sete referenciais visuais a partir dos seis ângulos, em graus."""
    transform = _identity()
    frames = [transform.copy()]
    for angle, (a, d, alpha) in zip(joint_angles_deg, DH_MODELS[robot_name]):
        transform = transform @ _dh_transform(math.radians(float(angle)), a, d, alpha)
        frames.append(transform.copy())
    visual_origins = VISUAL_ORIGINS[robot_name]
    return [
        frame @ _origin_transform(xyz, rpy)
        for frame, (xyz, rpy) in zip(frames, visual_origins)
    ]


def _to_qmatrix(matrix):
    values = [float(value) for value in matrix.reshape(-1)]
    return QMatrix4x4(*values)


class RobotArmView(QWidget):
    """Visualizador 3D com câmera orbitável e malhas separadas por junta."""

    def __init__(self, robot_name, parent=None):
        super().__init__(parent)
        if robot_name not in DH_MODELS:
            raise ValueError(f"Modelo UR não suportado: {robot_name}")
        self.robot_name = robot_name
        self.joint_angles_deg = [0.0] * 6
        self.mesh_items = []
        self.model_loaded = False

        self.stack = QStackedLayout(self)
        self.placeholder = QLabel()
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.placeholder.setObjectName("modelPlaceholder")
        self.placeholder.setMinimumSize(300, 270)
        self.stack.addWidget(self.placeholder)

        self.view = gl.GLViewWidget()
        self.view.setMinimumSize(300, 270)
        self.view.setBackgroundColor("#F7FAFC")
        self.view.opts["fov"] = 38
        self.stack.addWidget(self.view)

        self._add_reference_grid()
        self.load_model()

    def _add_reference_grid(self):
        grid = gl.GLGridItem()
        grid.setSize(x=1.25, y=1.25)
        grid.setSpacing(x=0.1, y=0.1)
        grid.setColor((0.72, 0.79, 0.83, 0.45))
        self.view.addItem(grid)
        axes = gl.GLAxisItem()
        axes.setSize(x=0.22, y=0.22, z=0.22)
        self.view.addItem(axes)

    def load_model(self):
        folder = model_cache_directory() / self.robot_name.lower() / "visual"
        missing = [name for name in LINK_NAMES if not (folder / f"{name}.dae").is_file()]
        if missing:
            self.placeholder.setText(
                "Modelo UR detalhado indisponível.\n"
                "Execute Iniciar_ELO.bat com internet para baixar as malhas visuais oficiais."
            )
            self.stack.setCurrentWidget(self.placeholder)
            return

        try:
            for link_name in LINK_NAMES:
                path = folder / f"{link_name}.dae"
                loaded = trimesh.load(path, force="scene", process=False)
                mesh = loaded.dump(concatenate=True)
                mesh_data = gl.MeshData(
                    vertexes=np.asarray(mesh.vertices, dtype=np.float32),
                    faces=np.asarray(mesh.faces, dtype=np.uint32),
                )
                mesh_item = gl.GLMeshItem(
                    meshdata=mesh_data,
                    color=LINK_COLORS[link_name],
                    smooth=True,
                    drawEdges=False,
                    shader="shaded",
                    glOptions="opaque",
                )
                self.view.addItem(mesh_item)
                self.mesh_items.append(mesh_item)

            distance = 0.85 if self.robot_name == "UR3e" else 1.35
            self.view.setCameraPosition(distance=distance, elevation=24, azimuth=42)
            self.model_loaded = True
            self.stack.setCurrentWidget(self.view)
            self.set_joint_angles(self.joint_angles_deg)
        except Exception as error:
            self.placeholder.setText(
                "Não foi possível carregar o modelo 3D.\n"
                f"Detalhe: {str(error)[:160]}"
            )
            self.stack.setCurrentWidget(self.placeholder)

    def set_joint_angles(self, angles_deg):
        values = [float(value) for value in angles_deg]
        if len(values) != 6:
            return
        self.joint_angles_deg = values
        if not self.model_loaded:
            return
        transforms = link_transforms(self.robot_name, values)
        for mesh_item, transform in zip(self.mesh_items, transforms):
            mesh_item.setTransform(_to_qmatrix(transform))

