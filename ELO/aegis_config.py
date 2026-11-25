"""Parâmetros do AEGIS que o operador pode ajustar na tela Configurações.

Ficam salvos em %LOCALAPPDATA%\\ELO\\aegis_config.json (fora do repositório,
então cada computador guarda os seus). Valores ausentes ou inválidos voltam
ao padrão.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PADROES = {
    "ip_leader": "10.104.11.99",
    "ip_follower": "10.104.11.71",
    "porta_garra": "auto",          # "auto" detecta pela câmera do punho
    "amortecimento": 0.015,         # 0..1
    "ganho_forca": 2.0,             # 0..2
    "f_entra_force": 1.1,           # N
    "f_sai_force": 0.6,             # N
    "reflexao": True,
    "k_reflexao": 0.1,              # N no leader por N no follower
    "zona_morta_reflexao": 60.0,    # N (gravação real: falsos contatos até ~53 N)
    "fmax_reflexao": 10.0,          # N
    # s; 0 = desligado. Ligado, um contato mantido some da mão e, ao soltar,
    # aparece um empurrão contrário: por isso fica desligado por padrão.
    "tau_vies_parado": 0.0,
}

# (mínimo, máximo) para os números; protege contra valores perigosos.
LIMITES = {
    "amortecimento": (0.0, 1.0),
    "ganho_forca": (0.0, 2.0),
    "f_entra_force": (0.2, 20.0),
    "f_sai_force": (0.1, 15.0),
    "tau_vies_parado": (0.0, 30.0),
    "k_reflexao": (0.0, 0.5),
    "zona_morta_reflexao": (0.0, 200.0),
    "fmax_reflexao": (0.0, 20.0),
}


def caminho() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "ELO" / "aegis_config.json"


def _validar(dados: dict) -> dict:
    cfg = dict(PADROES)
    for chave, padrao in PADROES.items():
        valor = dados.get(chave, padrao)
        try:
            if isinstance(padrao, bool):
                valor = bool(valor)
            elif isinstance(padrao, float):
                valor = float(valor)
                lo, hi = LIMITES.get(chave, (float("-inf"), float("inf")))
                valor = min(max(valor, lo), hi)
            else:
                valor = str(valor).strip() or padrao
        except (TypeError, ValueError):
            valor = padrao
        cfg[chave] = valor
    return cfg


def carregar() -> dict:
    try:
        return _validar(json.loads(caminho().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(PADROES)


def salvar(cfg: dict) -> dict:
    cfg = _validar(cfg)
    arquivo = caminho()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def portas_seriais() -> list[str]:
    """Lista as COMs disponíveis (vazio se o pyserial não estiver instalado)."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return sorted(p.device for p in list_ports.comports())
