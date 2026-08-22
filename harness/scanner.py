from dataclasses import dataclass
from pathlib import Path


EXCLUDED_DIRS = frozenset({"node_modules", "__pycache__", "venv", "dist", "build"})


@dataclass(frozen=True)
class FolderNode:
    path: Path
    children: tuple["FolderNode", ...] = ()


def scan_folders(root: Path) -> FolderNode:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    return _scan(root)


def _scan(folder: Path) -> FolderNode:
    try:
        candidates = sorted(folder.iterdir(), key=lambda path: path.name.casefold())
    except OSError:
        return FolderNode(folder)

    children = tuple(
        _scan(path)
        for path in candidates
        if _is_visible_directory(path)
    )
    return FolderNode(folder, children)


def _is_visible_directory(path: Path) -> bool:
    try:
        return (
            not path.name.startswith(".")
            and path.name not in EXCLUDED_DIRS
            and not path.is_symlink()
            and path.is_dir()
        )
    except OSError:
        return False
