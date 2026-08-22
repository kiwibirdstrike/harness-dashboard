import platform
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from harness import AGENT_COMMANDS


class LaunchError(RuntimeError):
    pass


@dataclass(frozen=True)
class LaunchSpec:
    argv: tuple[str, ...]
    cwd: Path | None = None
    creationflags: int = 0


def build_launch_spec(
    folder: Path, agent: str, system: str | None = None
) -> LaunchSpec:
    command = AGENT_COMMANDS.get(agent)
    if command is None:
        raise LaunchError(f"Unknown agent: {agent}")

    system = system or platform.system()
    if system == "Darwin":
        shell_command = f"cd {shlex.quote(str(folder))} && {command}"
        escaped_command = shell_command.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            'tell application "Terminal"\n'
            "activate\n"
            f'do script "{escaped_command}"\n'
            "end tell"
        )
        return LaunchSpec(("osascript", "-e", script))

    if system == "Windows":
        new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
        return LaunchSpec(
            ("cmd.exe", "/k", command),
            cwd=folder,
            creationflags=new_console,
        )

    raise LaunchError(f"Unsupported operating system: {system}")


def launch_agent(folder: Path, agent: str) -> None:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise LaunchError(f"Folder no longer exists: {folder}")

    spec = build_launch_spec(folder, agent)
    try:
        subprocess.Popen(
            spec.argv,
            cwd=spec.cwd,
            creationflags=spec.creationflags,
        )
    except OSError as error:
        raise LaunchError(f"Could not open terminal: {error}") from error
