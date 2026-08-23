from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
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
