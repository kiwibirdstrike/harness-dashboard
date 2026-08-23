from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from harness.agent_registry import Agent
from harness.launcher import validate_launch_command


@dataclass(frozen=True)
class WorkspaceEntry:
    folder: Path
    agent_name: str
    command: str
    title: str


@dataclass(frozen=True)
class WorkspaceSelection:
    entries: tuple[WorkspaceEntry, ...]
    skipped: tuple[str, ...]


class WorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceLaunchResult:
    session_name: str
    pane_count: int
    reused: bool
    tmux_path: Path


Runner = Callable[..., subprocess.CompletedProcess]


def workspace_session_name(root: Path) -> str:
    resolved = root.expanduser().resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", resolved.name.lower()).strip("-") or "project"
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:8]
    return f"harness-{slug[:32]}-{digest}"


def collect_workspace_entries(
    root: Path,
    assignments: Mapping[str, str],
    agents: Mapping[str, Agent],
) -> WorkspaceSelection:
    root = root.expanduser().resolve()
    entries: list[WorkspaceEntry] = []
    skipped: list[str] = []
    for key, agent_id in sorted(assignments.items()):
        agent = agents.get(agent_id)
        if agent is None:
            skipped.append(f"{key}: missing agent")
            continue
        folder = root if key == "." else root / key
        if not folder.is_dir():
            skipped.append(f"{key}: missing folder")
            continue
        entries.append(
            WorkspaceEntry(
                folder=folder,
                agent_name=agent.name,
                command=validate_launch_command(agent.command),
                title=f"{agent.name} · {folder.name or root.name}",
            )
        )
    return WorkspaceSelection(tuple(entries), tuple(skipped))


def find_tmux(
    *,
    which: Callable[[str], str | None] = shutil.which,
    is_file: Callable[[Path], bool] = Path.is_file,
) -> Path | None:
    from_path = which("tmux")
    candidates = tuple(
        candidate
        for candidate in (
            Path(from_path) if from_path else None,
            Path("/opt/homebrew/bin/tmux"),
            Path("/usr/local/bin/tmux"),
        )
        if candidate is not None
    )
    return next((candidate for candidate in candidates if is_file(candidate)), None)


def tmux_available() -> bool:
    return find_tmux() is not None


def _tmux_binary(tmux: str | Path | None) -> Path:
    binary = Path(tmux) if tmux is not None else find_tmux()
    if binary is None:
        raise WorkspaceError("tmux is required; install it with 'brew install tmux'")
    return binary


def _run(
    run: Runner,
    argv: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess:
    return run(tuple(argv), check=check, capture_output=True, text=True)


def _send_command(run: Runner, binary: Path, pane: str, command: str) -> None:
    command = validate_launch_command(command)
    _run(run, (str(binary), "send-keys", "-t", pane, "-l", "--", command))
    _run(run, (str(binary), "send-keys", "-t", pane, "Enter"))


def workspace_exists(
    root: Path,
    *,
    run: Runner = subprocess.run,
    tmux: str | Path | None = None,
) -> bool:
    session = workspace_session_name(root)
    binary = _tmux_binary(tmux)
    try:
        result = _run(run, (str(binary), "has-session", "-t", session), check=False)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError) as error:
        raise WorkspaceError(f"Could not inspect terminal workspace: {error}") from error


def start_workspace(
    root: Path,
    entries: tuple[WorkspaceEntry, ...],
    *,
    run: Runner = subprocess.run,
    tmux: str | Path | None = None,
) -> WorkspaceLaunchResult:
    session = workspace_session_name(root)
    binary = _tmux_binary(tmux)
    if workspace_exists(root, run=run, tmux=binary):
        result = _run(
            run,
            (str(binary), "list-panes", "-t", f"{session}:0", "-F", "#{pane_id}"),
        )
        return WorkspaceLaunchResult(
            session,
            len(result.stdout.splitlines()),
            True,
            binary,
        )
    if not entries:
        raise WorkspaceError("No valid assigned folders to launch")

    created = False
    try:
        first = entries[0]
        _run(
            run,
            (
                str(binary),
                "new-session",
                "-d",
                "-x",
                "200",
                "-y",
                "60",
                "-s",
                session,
                "-c",
                str(first.folder),
            ),
        )
        created = True
        target = f"{session}:0"
        _run(run, (str(binary), "select-pane", "-t", f"{target}.0", "-T", first.title))
        _run(run, (str(binary), "set-option", "-w", "-t", target, "remain-on-exit", "on"))
        _run(run, (str(binary), "set-option", "-w", "-t", target, "pane-border-status", "top"))
        _run(
            run,
            (str(binary), "set-option", "-w", "-t", target, "pane-border-format", " #{pane_title} "),
        )
        _run(
            run,
            (
                str(binary),
                "set-hook",
                "-t",
                session,
                "after-kill-pane",
                f"select-layout -t {target} tiled",
            ),
        )
        _send_command(run, binary, f"{target}.0", first.command)
        for entry in entries[1:]:
            pane = _run(
                run,
                (
                    str(binary),
                    "split-window",
                    "-d",
                    "-P",
                    "-F",
                    "#{pane_id}",
                    "-t",
                    target,
                    "-c",
                    str(entry.folder),
                ),
            ).stdout.strip()
            if not pane:
                raise WorkspaceError("tmux did not return the new pane ID")
            _run(run, (str(binary), "select-pane", "-t", pane, "-T", entry.title))
            _send_command(run, binary, pane, entry.command)
            _run(run, (str(binary), "select-layout", "-t", target, "tiled"))
        if len(entries) == 1:
            _run(run, (str(binary), "select-layout", "-t", target, "tiled"))
        return WorkspaceLaunchResult(session, len(entries), False, binary)
    except (OSError, subprocess.SubprocessError, WorkspaceError) as error:
        if created:
            _run(run, (str(binary), "kill-session", "-t", session), check=False)
        raise WorkspaceError(f"Could not create terminal workspace: {error}") from error


def stop_workspace(
    root: Path,
    *,
    run: Runner = subprocess.run,
    tmux: str | Path | None = None,
) -> None:
    binary = _tmux_binary(tmux)
    try:
        _run(run, (str(binary), "kill-session", "-t", workspace_session_name(root)))
    except (OSError, subprocess.SubprocessError) as error:
        raise WorkspaceError(f"Could not stop terminal workspace: {error}") from error
