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
ROBOT_COLORS = {
    # Verde-água para o UR3e Leader.
    "UR3e": {
        "base": (0.08, 0.40, 0.44, 1.0),
        "shoulder": (0.08, 0.58, 0.60, 1.0),
        "upperarm": (0.12, 0.78, 0.74, 1.0),
        "forearm": (0.05, 0.67, 0.70, 1.0),
        "wrist1": (0.20, 0.74, 0.76, 1.0),
        "wrist2": (0.14, 0.62, 0.66, 1.0),
        "wrist3": (0.07, 0.50, 0.57, 1.0),
    },
    # Azul para o UR5e Follower.
    "UR5e": {
        "base": (0.14, 0.30, 0.58, 1.0),
        "shoulder": (0.21, 0.42, 0.73, 1.0),
        "upperarm": (0.30, 0.59, 0.91, 1.0),
        "forearm": (0.20, 0.49, 0.83, 1.0),
        "wrist1": (0.34, 0.59, 0.86, 1.0),
        "wrist2": (0.29, 0.68, 0.95, 1.0),
        "wrist3": (0.17, 0.39, 0.73, 1.0),
    },
}

# Origem fixa de cada junta no elo anterior (xyz em metros; rpy em radianos),
# conforme a cadeia de elos do URDF oficial da Universal Robots.
JOINT_ORIGINS = {
    "UR3e": (
        ((0.0, 0.0, 0.15185), (0.0, 0.0, 0.0)),
        ((0.0, 0.0, 0.0), (math.pi / 2, 0.0, 0.0)),
        ((-0.24355, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((-0.2132, 0.0, 0.13105), (0.0, 0.0, 0.0)),
        ((0.0, -0.08535, 0.0), (math.pi / 2, 0.0, 0.0)),
        ((0.0, 0.0921, 0.0), (math.pi / 2, math.pi, math.pi)),
    ),
    "UR5e": (
        ((0.0, 0.0, 0.1625), (0.0, 0.0, 0.0)),
        ((0.0, 0.0, 0.0), (math.pi / 2, 0.0, 0.0)),
        ((-0.425, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((-0.3922, 0.0, 0.1333), (0.0, 0.0, 0.0)),
        ((0.0, -0.0997, 0.0), (math.pi / 2, 0.0, 0.0)),
        ((0.0, 0.0996, 0.0), (math.pi / 2, math.pi, math.pi)),
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


def link_frames(robot_name, joint_angles_deg):
    """Calcula os referenciais dos elos pela cadeia de juntas do URDF."""
    transform = _identity()
    frames = [transform.copy()]
    for angle, (xyz, rpy) in zip(joint_angles_deg, JOINT_ORIGINS[robot_name]):
        joint_origin = _origin_transform(xyz, rpy)
        theta = math.radians(float(angle))
        joint_rotation = _identity()
        joint_rotation[:3, :3] = np.array(
            [
                [math.cos(theta), -math.sin(theta), 0.0],
                [math.sin(theta), math.cos(theta), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        transform = transform @ joint_origin @ joint_rotation
        frames.append(transform.copy())
    return frames


def link_transforms(robot_name, joint_angles_deg):
    """Calcula as transformações visuais de cada elo a partir dos ângulos."""
    frames = link_frames(robot_name, joint_angles_deg)
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
        if robot_name not in JOINT_ORIGINS:
            raise ValueError(f"Modelo UR não suportado: {robot_name}")
        self.robot_name = robot_name
        self.joint_angles_deg = [0.0] * 6
        self.gripper_position = 0
        self.mesh_items = []
        self.gripper_items = []
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
                    color=ROBOT_COLORS[self.robot_name][link_name],
                    smooth=True,
                    drawEdges=False,
                    shader="edgeHilight",
                    glOptions="opaque",
                )
                self.view.addItem(mesh_item)
                self.mesh_items.append(mesh_item)

            if self.robot_name == "UR5e":
                self._add_demo_gripper()

            distance = 0.85 if self.robot_name == "UR3e" else 1.35
            target_height = 0.22 if self.robot_name == "UR3e" else 0.34
            self.view.opts["center"] = QVector3D(0.0, 0.0, target_height)
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

    def _add_demo_gripper(self):
        """Desenha uma garra paralela simples no flange do UR5e."""
        parts = (
            ((0.120, 0.082, 0.050), (0.10, 0.16, 0.20, 1.0)),
            ((0.016, 0.034, 0.085), (0.16, 0.25, 0.29, 1.0)),
            ((0.016, 0.034, 0.085), (0.16, 0.25, 0.29, 1.0)),
            ((0.006, 0.036, 0.060), (0.12, 0.66, 0.63, 1.0)),
            ((0.006, 0.036, 0.060), (0.12, 0.66, 0.63, 1.0)),
        )
        for size, color in parts:
            mesh = trimesh.creation.box(extents=size)
            mesh_data = gl.MeshData(
                vertexes=np.asarray(mesh.vertices, dtype=np.float32),
                faces=np.asarray(mesh.faces, dtype=np.uint32),
            )
            item = gl.GLMeshItem(
                meshdata=mesh_data,
                color=color,
                smooth=False,
                drawEdges=False,
                shader="edgeHilight",
                glOptions="opaque",
            )
            self.view.addItem(item)
            self.gripper_items.append(item)

    @staticmethod
    def _translation(x, y, z):
        transform = _identity()
        transform[:3, 3] = (x, y, z)
        return transform

    def _update_demo_gripper(self, wrist_frame):
        if not self.gripper_items:
            return
        closed_fraction = self.gripper_position / 255.0
        center_spacing = 0.016 + 0.085 * (1.0 - closed_fraction)
        half_spacing = center_spacing / 2.0
        finger_width = 0.016
        pad_width = 0.006
        # Base, dedos esquerdo/direito e suas duas superfícies internas.
        local_transforms = [self._translation(0.0, 0.0, 0.025)]
        for side in (-1.0, 1.0):
            local_transforms.append(
                self._translation(side * half_spacing, 0.0, 0.085)
            )
        for side in (-1.0, 1.0):
            pad_x = side * (half_spacing - finger_width / 2.0 - pad_width / 2.0)
            local_transforms.append(self._translation(pad_x, 0.0, 0.085))
        for item, local_transform in zip(self.gripper_items, local_transforms):
            item.setTransform(_to_qmatrix(wrist_frame @ local_transform))

    def set_gripper_position(self, position):
        """Atualiza abertura da garra: 0 totalmente aberta, 255 fechada."""
        self.gripper_position = max(0, min(255, int(position)))
        if self.model_loaded and self.robot_name == "UR5e":
            frames = link_frames(self.robot_name, self.joint_angles_deg)
            self._update_demo_gripper(frames[-1])

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
        if self.robot_name == "UR5e":
            frames = link_frames(self.robot_name, values)
            self._update_demo_gripper(frames[-1])

