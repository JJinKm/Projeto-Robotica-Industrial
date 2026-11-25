"""Modelo do desvio do sensor de força do leader (UR3e) em função da orientação.

Com a ferramenta parada e ninguém encostando, o sensor do UR3e ainda mede
uma força falsa que muda com a orientação: o payload configurado (0,05 kg)
não bate com o que está montado no flange, e o zero do sensor fica no
referencial dele. Pela física, essa leitura falsa no referencial da base é

    F_falsa(R) = a + R · b

a: erro de peso (vertical, constante na base); b: zero do sensor (gira com
a ferramenta); R: orientação da ferramenta. Com amostras paradas em algumas
orientações, a e b saem por mínimos quadrados, e o AEGIS desconta a força
falsa em qualquer pose. Sem isso, o leader solto numa pose diferente da de
Home ficava em force mode e andava sozinho.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np


def rotvec_para_matriz(rv) -> np.ndarray:
    """Rotação (vetor de rotação do UR, em rad) para matriz 3x3 (Rodrigues)."""
    rv = np.asarray(rv[:3], dtype=float)
    ang = float(np.linalg.norm(rv))
    if ang < 1e-9:
        return np.eye(3)
    k = rv / ang
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


class ModeloSensorLeader:
    """Amostras "fixas" vêm da varredura do punho (orientações variadas) e
    nunca saem; as "online" vêm do leader parado durante a operação e
    acompanham poses novas e o aquecimento do sensor, sem apagar a varredura."""

    MAX_ONLINE = 40
    ANG_MESMA_POSE = math.radians(4)

    def __init__(self):
        self.fixas: list = []
        self.online: deque = deque(maxlen=self.MAX_ONLINE)
        self.a = np.zeros(3)
        self.b = np.zeros(3)
        self.pronto = False
        self.erro_rms = None

    def limpar(self):
        self.fixas.clear()
        self.online.clear()
        self.a = np.zeros(3)
        self.b = np.zeros(3)
        self.pronto = False
        self.erro_rms = None

    def adicionar(self, pose_tcp, forca, fixa: bool = True) -> None:
        amostra = (rotvec_para_matriz(pose_tcp[3:6]), np.asarray(forca[:3], dtype=float))
        if fixa:
            self.fixas.append(amostra)
            return
        # Mesma orientação de uma amostra online recente: substitui (uma
        # pose parada por muito tempo não pesa mais que as outras).
        for i, (R, _) in enumerate(self.online):
            cos_ang = (np.trace(R.T @ amostra[0]) - 1) / 2
            if math.acos(max(-1.0, min(1.0, cos_ang))) < self.ANG_MESMA_POSE:
                del self.online[i]
                break
        self.online.append(amostra)

    @property
    def amostras(self):
        return list(self.fixas) + list(self.online)

    def ajustar(self) -> bool:
        """Mínimos quadrados de [a; b]. Precisa de orientações variadas."""
        amostras = self.amostras
        if len(amostras) < 4:
            return False
        linhas, alvo = [], []
        for R, f in amostras:
            linhas.append(np.hstack([np.eye(3), R]))
            alvo.append(f)
        A = np.vstack(linhas)
        y = np.concatenate(alvo)
        # Regularização leve: com pouca variação de orientação, prefere
        # valores pequenos em vez de explodir a e b em sentidos opostos.
        lam = 1e-2
        A_reg = np.vstack([A, math.sqrt(lam) * np.eye(6)])
        y_reg = np.concatenate([y, np.zeros(6)])
        x, *_ = np.linalg.lstsq(A_reg, y_reg, rcond=None)
        self.a, self.b = x[:3], x[3:]
        residuo = A @ x - y
        self.erro_rms = float(math.sqrt(np.mean(residuo ** 2)))
        self.pronto = True
        return True

    def prever(self, pose_tcp) -> np.ndarray:
        if not self.pronto:
            return np.zeros(3)
        return self.a + rotvec_para_matriz(pose_tcp[3:6]) @ self.b

    def corrigir(self, pose_tcp, forca) -> np.ndarray:
        """Força do leader sem o desvio do sensor (referencial da base)."""
        return np.asarray(forca[:3], dtype=float) - self.prever(pose_tcp)
