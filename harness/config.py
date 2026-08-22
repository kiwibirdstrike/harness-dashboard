import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from harness import AGENT_COMMANDS


CONFIG_NAME = ".harness.json"


class ConfigError(ValueError):
    pass


def load_assignments(root: Path) -> dict[str, str]:
    config_path = root / CONFIG_NAME
    if not config_path.exists():
        return {}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"Cannot read {config_path}: {error}") from error

    if not isinstance(data, dict) or data.get("version") != 1:
        raise ConfigError(f"Unsupported configuration in {config_path}")

    assignments = data.get("assignments")
    if not isinstance(assignments, dict):
        raise ConfigError(f"Invalid assignments in {config_path}")

    return {
        key: agent
        for key, agent in assignments.items()
        if isinstance(key, str)
        and _valid_key(key)
        and isinstance(agent, str)
        and agent in AGENT_COMMANDS
    }


def save_assignments(root: Path, assignments: Mapping[str, str]) -> None:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ConfigError(f"Not a directory: {root}")
    if any(not _valid_key(key) or agent not in AGENT_COMMANDS for key, agent in assignments.items()):
        raise ConfigError("Assignments must use project-relative paths and known agents")

    config_path = root / CONFIG_NAME
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=root,
            prefix=".harness.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(
                {"version": 1, "assignments": dict(assignments)},
                temporary,
                indent=2,
                sort_keys=True,
            )
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, config_path)
    except OSError as error:
        raise ConfigError(f"Cannot save {config_path}: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _valid_key(key: str) -> bool:
    if not key:
        return False
    path = PurePosixPath(key)
    return not path.is_absolute() and ".." not in path.parts
