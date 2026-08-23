from __future__ import annotations

import platform
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

class LaunchError(RuntimeError):
    pass


@dataclass(frozen=True)
class LaunchSpec:
    argv: tuple[str, ...]
    cwd: Path | None = None
    creationflags: int = 0


def validate_launch_command(command: str) -> str:
    command = command.strip()
    if not command or any(character in command for character in "\r\n\0"):
        raise LaunchError("Launch command must be one line")
    return command


def build_launch_spec(
    folder: Path, command: str, system: str | None = None
) -> LaunchSpec:
    command = validate_launch_command(command)

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


def build_open_folder_spec(folder: Path, system: str | None = None) -> LaunchSpec:
    system = system or platform.system()
    if system == "Darwin":
        return LaunchSpec(("open", str(folder)))
    if system == "Windows":
        return LaunchSpec(("explorer.exe", str(folder)))
    raise LaunchError(f"Unsupported operating system: {system}")


def find_iterm_app(
    *,
    home: Path | None = None,
    is_dir: Callable[[Path], bool] = Path.is_dir,
) -> Path | None:
    home = Path.home() if home is None else home
    for candidate in (Path("/Applications/iTerm.app"), home / "Applications/iTerm.app"):
        if is_dir(candidate):
            return candidate
    return None


def build_workspace_attach_spec(
    session_name: str,
    tmux_path: Path,
    *,
    use_iterm: bool,
) -> LaunchSpec:
    if not re.fullmatch(r"[a-z0-9-]+", session_name):
        raise LaunchError("Invalid workspace session name")
    binary = shlex.quote(str(tmux_path))
    if use_iterm:
        command = _escape_applescript_text(
            f"{binary} -CC attach -t {session_name}"
        )
        script = (
            'tell application "iTerm2"\n'
            "activate\n"
            "set newWindow to (create window with default profile)\n"
            f'tell current session of newWindow to write text "{command}"\n'
            "end tell"
        )
    else:
        command = _escape_applescript_text(f"{binary} attach -t {session_name}")
        script = (
            'tell application "Terminal"\n'
            "activate\n"
            f'do script "{command}"\n'
            "end tell"
        )
    return LaunchSpec(("osascript", "-e", script))


def _escape_applescript_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def launch_agent(folder: Path, command: str) -> None:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise LaunchError(f"Folder no longer exists: {folder}")

    spec = build_launch_spec(folder, command)
    try:
        subprocess.Popen(
            spec.argv,
            cwd=spec.cwd,
            creationflags=spec.creationflags,
        )
    except OSError as error:
        raise LaunchError(f"Could not open terminal: {error}") from error


def open_folder(folder: Path) -> None:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise LaunchError(f"Folder no longer exists: {folder}")
    spec = build_open_folder_spec(folder)
    try:
        subprocess.Popen(spec.argv)
    except OSError as error:
        raise LaunchError(f"Could not open folder: {error}") from error


def launch_workspace(session_name: str, tmux_path: Path) -> str:
    application = "iTerm2" if find_iterm_app() else "Terminal"
    spec = build_workspace_attach_spec(
        session_name,
        tmux_path,
        use_iterm=application == "iTerm2",
    )
    try:
        subprocess.Popen(spec.argv)
    except OSError as error:
        raise LaunchError(f"Could not open terminal workspace: {error}") from error
    return application
