"""Baixa os modelos visuais UR3e/UR5e da descrição oficial da Universal Robots."""

import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


BASE_URL = (
    "https://raw.githubusercontent.com/UniversalRobots/"
    "Universal_Robots_ROS2_Description/rolling"
)
LINKS = ("base", "shoulder", "upperarm", "forearm", "wrist1", "wrist2", "wrist3")
ROBOTS = ("ur3e", "ur5e")


def cache_root():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ELO" / "models"
    return Path.home() / ".local" / "share" / "ELO" / "models"


def download(url, destination):
    request = Request(url, headers={"User-Agent": "ELO-Robotics-Interface/1.0"})
    with urlopen(request, timeout=35) as response:
        content = response.read()
    if len(content) < 1024 or b"<COLLADA" not in content[:4096]:
        raise ValueError("o arquivo recebido não parece uma malha DAE válida")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def main():
    root = cache_root()
    failures = []
    total = len(ROBOTS) * len(LINKS)
    current = 0
    for robot in ROBOTS:
        for link in LINKS:
            current += 1
            destination = root / robot / "visual" / f"{link}.dae"
            if destination.is_file() and destination.stat().st_size > 1024:
                print(f"[{current}/{total}] Modelo já existe: {robot}/{link}")
                continue
            url = f"{BASE_URL}/meshes/{robot}/visual/{link}.dae"
            try:
                print(f"[{current}/{total}] Baixando modelo {robot}/{link}...")
                download(url, destination)
            except (URLError, TimeoutError, OSError, ValueError) as error:
                failures.append(f"{robot}/{link}: {error}")

    license_path = root / "LICENSE"
    if not license_path.is_file():
        try:
            request = Request(f"{BASE_URL}/LICENSE", headers={"User-Agent": "ELO-Robotics-Interface/1.0"})
            with urlopen(request, timeout=20) as response:
                license_path.write_bytes(response.read())
        except (URLError, TimeoutError, OSError):
            pass

    if failures:
        print("\nNão foi possível baixar todas as malhas. A interface ainda abrirá:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(f"\nModelos UR3e e UR5e preparados em: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
