from __future__ import annotations

import os
import platform
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_command(system: str | None = None) -> list[str]:
    system = system or platform.system()
    if system not in {"Darwin", "Windows"}:
        raise RuntimeError(f"Unsupported build platform: {system}")
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "HarnessDashboard",
        "app.py",
    ]


def build_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    result = dict(os.environ if environment is None else environment)
    result["PYINSTALLER_CONFIG_DIR"] = str(
        PROJECT_ROOT / "build" / ".pyinstaller-config"
    )
    return result


def main() -> None:
    subprocess.run(
        build_command(),
        cwd=PROJECT_ROOT,
        env=build_environment(),
        check=True,
    )


if __name__ == "__main__":
    main()
