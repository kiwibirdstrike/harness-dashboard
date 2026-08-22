from __future__ import annotations

import json
import os
import platform
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


ACCENT_COLORS = ("#7C3AED", "#0EA5E9", "#D97706", "#16A34A", "#DC2626", "#DB2777")


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    command: str
    image: str | None
    color: str


def app_data_dir(
    system: str | None = None,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    system = system or platform.system()
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    if system == "Darwin":
        return home / "Library" / "Application Support" / "HarnessDashboard"
    if system == "Windows":
        appdata = environ.get("APPDATA")
        if not appdata:
            raise RegistryError("APPDATA is not available")
        return Path(appdata) / "HarnessDashboard"
    return home / ".harness-dashboard"


class AgentRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_data_dir()
        self.path = self.root / "agents.json"

    def load(self) -> list[Agent]:
        if not self.path.exists():
            agents = [
                Agent(str(uuid.uuid4()), name, command, None, color)
                for name, command, color in (
                    ("Codex", "codex", ACCENT_COLORS[0]),
                    ("Claude", "claude", ACCENT_COLORS[1]),
                    ("Gemini", "gemini", ACCENT_COLORS[2]),
                )
            ]
            self._save(agents)
            return agents
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("unsupported version")
            return [Agent(**item) for item in data["agents"]]
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RegistryError(f"Cannot read {self.path}: {error}") from error

    def delete(self, agent_id: str) -> None:
        agents = self.load()
        removed = next((agent for agent in agents if agent.id == agent_id), None)
        kept = [agent for agent in agents if agent.id != agent_id]
        if removed is None:
            raise RegistryError("Agent not found")
        self._save(kept)
        self._delete_image(removed.image)

    def add(
        self, name: str, command: str, image: Path | None, color: str
    ) -> Agent:
        name, command = self._validate_fields(name, command, color)
        agent_id = str(uuid.uuid4())
        existing = self.load()
        copied_image, staged = self._stage_image(agent_id, image)
        agent = Agent(agent_id, name, command, copied_image, color)
        saved = False
        try:
            self._save([*existing, agent])
            saved = True
            self._install_image(copied_image, staged)
        except RegistryError:
            if saved:
                self._save(existing)
            raise
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        return agent

    def update(
        self,
        agent_id: str,
        name: str,
        command: str,
        image: Path | None,
        color: str,
    ) -> Agent:
        name, command = self._validate_fields(name, command, color)
        agents = self.load()
        previous = next((agent for agent in agents if agent.id == agent_id), None)
        if previous is None:
            raise RegistryError("Agent not found")
        copied_image, staged = self._stage_image(agent_id, image)
        updated = Agent(agent_id, name, command, copied_image, color)
        saved = False
        try:
            self._save([updated if agent.id == agent_id else agent for agent in agents])
            saved = True
            self._install_image(copied_image, staged)
        except RegistryError:
            if saved:
                self._save(agents)
            raise
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        if previous.image != copied_image:
            self._delete_image(previous.image)
        return updated

    @staticmethod
    def _validate_fields(name: str, command: str, color: str) -> tuple[str, str]:
        name = name.strip()
        command = command.strip()
        if not name or any(character in name for character in "\r\n\0"):
            raise RegistryError("Agent name is required")
        if not command or any(character in command for character in "\r\n\0"):
            raise RegistryError("Launch command must be one line")
        if color not in ACCENT_COLORS:
            raise RegistryError("Choose a supported accent color")
        return name, command

    def _stage_image(
        self, agent_id: str, source: Path | None
    ) -> tuple[str | None, Path | None]:
        if source is None:
            return None, None
        source = source.expanduser().resolve()
        try:
            with source.open("rb") as image_file:
                signature = image_file.read(8)
            if source.suffix.lower() != ".png" or signature != b"\x89PNG\r\n\x1a\n":
                raise RegistryError("Signature image must be a PNG")
            images = self.root / "images"
            images.mkdir(parents=True, exist_ok=True)
            destination = images / f"{agent_id}.png"
            relative = destination.relative_to(self.root).as_posix()
            if source == destination.resolve():
                return relative, None
            with tempfile.NamedTemporaryFile(
                "wb", dir=images, prefix=f"{agent_id}.", suffix=".tmp", delete=False
            ) as temporary:
                staged = Path(temporary.name)
                with source.open("rb") as image_file:
                    shutil.copyfileobj(image_file, temporary)
                temporary.flush()
                os.fsync(temporary.fileno())
            return relative, staged
        except OSError as error:
            raise RegistryError(f"Cannot copy signature image: {error}") from error

    def _install_image(self, relative_path: str | None, staged: Path | None) -> None:
        if relative_path and staged is not None:
            try:
                os.replace(staged, self.root / relative_path)
            except OSError as error:
                raise RegistryError(f"Cannot install signature image: {error}") from error

    def _delete_image(self, relative_path: str | None) -> None:
        if not relative_path:
            return
        path = (self.root / relative_path).resolve()
        images = (self.root / "images").resolve()
        if path.parent == images:
            path.unlink(missing_ok=True)

    def _save(self, agents: list[Agent]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.root, prefix="agents.", suffix=".tmp", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(
                    {"version": 1, "agents": [asdict(agent) for agent in agents]},
                    temporary,
                    indent=2,
                )
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise RegistryError(f"Cannot save {self.path}: {error}") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
