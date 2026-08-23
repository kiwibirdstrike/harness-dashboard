# Adaptive iTerm2 + tmux Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open every valid assigned Agent CLI in one persistent iTerm2 workspace whose tmux panes automatically use the built-in tiled layout.

**Architecture:** A focused `harness/workspace.py` module converts assignments into launch entries and owns the Harness tmux session lifecycle. `harness/launcher.py` remains the native application boundary and opens iTerm2 in tmux control mode, with built-in Terminal as fallback. `app.py` adds project-level open/show/stop controls without changing the existing single-folder terminal action.

**Tech Stack:** Python 3.10+, Tkinter/ttk, Python standard library (`dataclasses`, `hashlib`, `pathlib`, `re`, `shutil`, `subprocess`), tmux, iTerm2, `unittest`

**Spec:** `docs/superpowers/specs/2026-08-23-adaptive-tmux-workspace-design.md`

## Global Constraints

- The first implementation is macOS-only.
- Use iTerm2 as the preferred visible terminal application and built-in Terminal as the automatic fallback.
- Use `tmux select-layout tiled`; do not implement custom pane geometry.
- Do not install or update iTerm2 or tmux automatically.
- Preserve the current single-folder **Open Terminal** behavior.
- Existing session names must be stable per absolute project path and must not collide for equal folder names.
- Stop only the tmux session owned by the selected Harness project.
- Keep configured Agent commands one-line validated and pass paths as separate process arguments.

---

### Task 1: Workspace Entries and Stable Session Identity

**Files:**
- Create: `harness/workspace.py`
- Modify: `harness/launcher.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: `Agent` from `harness.agent_registry`; project-relative assignment keys already produced by `assignment_key()`.
- Produces: `WorkspaceEntry`, `WorkspaceSelection`, `collect_workspace_entries()`, `workspace_session_name()`, and `validate_launch_command()` for later tasks.

- [ ] **Step 1: Write failing tests for command validation, entry filtering, and session identity**

Add these imports and tests to `tests/test_harness.py`:

```python
from harness.launcher import validate_launch_command
from harness.workspace import collect_workspace_entries, workspace_session_name


class WorkspaceSelectionTests(unittest.TestCase):
    def test_collects_valid_entries_and_reports_invalid_assignments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "src").mkdir()
            agents = {
                "codex": Agent("codex", "Codex", "codex", None, "#7C3AED"),
            }

            selection = collect_workspace_entries(
                root,
                {".": "codex", "src": "codex", "gone": "codex", "docs": "deleted"},
                agents,
            )

            self.assertEqual([entry.folder for entry in selection.entries], [root, root / "src"])
            self.assertEqual(selection.entries[1].title, "Codex · src")
            self.assertEqual(selection.skipped, ("docs: missing agent", "gone: missing folder"))

    def test_session_name_is_stable_and_path_specific(self):
        first = workspace_session_name(Path("/tmp/one/Project"))
        second = workspace_session_name(Path("/tmp/two/Project"))

        self.assertEqual(first, workspace_session_name(Path("/tmp/one/Project")))
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^harness-project-[0-9a-f]{8}$")


class LaunchCommandValidationTests(unittest.TestCase):
    def test_rejects_empty_and_multiline_commands(self):
        self.assertEqual(validate_launch_command(" codex --fast "), "codex --fast")
        for command in ("", "codex\nrm", "codex\0bad"):
            with self.assertRaises(LaunchError):
                validate_launch_command(command)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_harness.WorkspaceSelectionTests \
  tests.test_harness.LaunchCommandValidationTests -v
```

Expected: import errors because `harness.workspace` and `validate_launch_command` do not exist.

- [ ] **Step 3: Expose the existing one-line validator and add the workspace value objects**

In `harness/launcher.py`, extract the current validation from `build_launch_spec()`:

```python
def validate_launch_command(command: str) -> str:
    command = command.strip()
    if not command or any(character in command for character in "\r\n\0"):
        raise LaunchError("Launch command must be one line")
    return command
```

Call `validate_launch_command(command)` from `build_launch_spec()`.

Create `harness/workspace.py` with:

```python
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
```

- [ ] **Step 4: Run focused and full tests**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_harness.WorkspaceSelectionTests \
  tests.test_harness.LaunchCommandValidationTests -v
.venv/bin/python -m unittest tests.test_harness -q
```

Expected: focused tests pass; all existing tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add harness/workspace.py harness/launcher.py tests/test_harness.py
git commit -m "Define safe terminal workspace entries"
```

---

### Task 2: tmux Session Lifecycle and Tiled Layout

**Files:**
- Modify: `harness/workspace.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: `WorkspaceEntry` and `workspace_session_name()` from Task 1.
- Produces: `WorkspaceError`, `WorkspaceLaunchResult`, `find_tmux()`, `tmux_available()`, `workspace_exists()`, `start_workspace()`, and `stop_workspace()`.

- [ ] **Step 1: Write failing lifecycle tests using a fake process runner**

Add to `tests/test_harness.py`:

```python
from harness.workspace import (
    WorkspaceEntry,
    WorkspaceError,
    find_tmux,
    start_workspace,
    stop_workspace,
    workspace_exists,
)


class Completed:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class TmuxWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("/tmp/project")
        self.entries = (
            WorkspaceEntry(self.root, "Codex", "codex", "Codex · project"),
            WorkspaceEntry(self.root / "docs", "Claude", "claude", "Claude · docs"),
        )

    def test_creates_panes_titles_and_tiled_layout(self):
        calls = []

        def run(argv, **kwargs):
            calls.append((tuple(argv), kwargs))
            if argv[1] == "has-session":
                return Completed(1)
            if argv[1] == "split-window":
                return Completed(stdout="%1\n")
            return Completed()

        result = start_workspace(self.root, self.entries, run=run, tmux="tmux")

        self.assertFalse(result.reused)
        self.assertEqual(result.pane_count, 2)
        self.assertTrue(any("new-session" in argv for argv, _ in calls))
        self.assertTrue(any("split-window" in argv for argv, _ in calls))
        self.assertTrue(any(argv[-1] == "tiled" for argv, _ in calls))
        self.assertEqual(sum("select-pane" in argv for argv, _ in calls), 2)
        self.assertTrue(any("remain-on-exit" in argv for argv, _ in calls))
        self.assertTrue(any("after-kill-pane" in argv for argv, _ in calls))

    def test_existing_session_is_reused_without_starting_agents(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(tuple(argv))
            if argv[1] == "list-panes":
                return Completed(stdout="%0\n%1\n")
            return Completed()

        result = start_workspace(self.root, self.entries, run=run, tmux="tmux")

        self.assertTrue(result.reused)
        self.assertEqual(len(calls), 2)
        self.assertIn("has-session", calls[0])
        self.assertIn("list-panes", calls[1])

    def test_partial_failure_kills_only_the_new_session(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(tuple(argv))
            if argv[1] == "has-session":
                return Completed(1)
            if argv[1] == "split-window":
                raise subprocess.CalledProcessError(1, argv)
            return Completed()

        with self.assertRaises(WorkspaceError):
            start_workspace(self.root, self.entries, run=run, tmux="tmux")

        self.assertIn("kill-session", calls[-1])

    def test_stop_targets_the_project_session(self):
        calls = []
        stop_workspace(
            self.root,
            run=lambda argv, **kwargs: calls.append(tuple(argv)) or Completed(),
            tmux="tmux",
        )
        self.assertEqual(calls[0][1], "kill-session")
        self.assertEqual(calls[0][2], "-t")

    def test_finds_homebrew_tmux_when_gui_path_is_empty(self):
        homebrew = Path("/opt/homebrew/bin/tmux")
        found = find_tmux(
            which=lambda _name: None,
            is_file=lambda path: path == homebrew,
        )
        self.assertEqual(found, homebrew)
```

- [ ] **Step 2: Run the lifecycle tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_harness.TmuxWorkspaceTests -v
```

Expected: import errors for the lifecycle API.

- [ ] **Step 3: Implement the minimum tmux controller in `harness/workspace.py`**

Add:

```python
import shutil
import subprocess
from collections.abc import Callable, Sequence


class WorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceLaunchResult:
    session_name: str
    pane_count: int
    reused: bool
    tmux_path: Path


Runner = Callable[..., subprocess.CompletedProcess]


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


def _run(run: Runner, argv: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return run(tuple(argv), check=check, capture_output=True, text=True)


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
    if not entries:
        raise WorkspaceError("No valid assigned folders to launch")
    session = workspace_session_name(root)
    binary = _tmux_binary(tmux)
    if workspace_exists(root, run=run, tmux=binary):
        result = _run(run, (str(binary), "list-panes", "-t", f"{session}:0", "-F", "#{pane_id}"))
        pane_count = len(result.stdout.splitlines())
        return WorkspaceLaunchResult(session, pane_count, True, binary)
    created = False
    try:
        first = entries[0]
        _run(run, (str(binary), "new-session", "-d", "-s", session, "-c", str(first.folder), first.command))
        created = True
        _run(run, (str(binary), "select-pane", "-t", f"{session}:0.0", "-T", first.title))
        _run(run, (str(binary), "set-option", "-w", "-t", f"{session}:0", "remain-on-exit", "on"))
        _run(run, (str(binary), "set-option", "-w", "-t", f"{session}:0", "pane-border-status", "top"))
        _run(run, (str(binary), "set-option", "-w", "-t", f"{session}:0", "pane-border-format", " #{pane_title} "))
        _run(run, (str(binary), "set-hook", "-t", session, "after-kill-pane", f"select-layout -t {session}:0 tiled"))
        for entry in entries[1:]:
            pane = _run(
                run,
                (str(binary), "split-window", "-d", "-P", "-F", "#{pane_id}", "-t", f"{session}:0", "-c", str(entry.folder), entry.command),
            ).stdout.strip()
            if not pane:
                raise WorkspaceError("tmux did not return the new pane ID")
            _run(run, (str(binary), "select-pane", "-t", pane, "-T", entry.title))
        _run(run, (str(binary), "select-layout", "-t", f"{session}:0", "tiled"))
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
```

- [ ] **Step 4: Run lifecycle and full tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_harness.TmuxWorkspaceTests -v
.venv/bin/python -m unittest tests.test_harness -q
```

Expected: all tests pass and every created workspace ends with `select-layout tiled`.

- [ ] **Step 5: Commit Task 2**

```bash
git add harness/workspace.py tests/test_harness.py
git commit -m "Manage persistent tiled tmux workspaces"
```

---

### Task 3: Preferred iTerm2 Attach with Terminal Fallback

**Files:**
- Modify: `harness/launcher.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: the stable `session_name` and absolute `tmux_path` returned by `start_workspace()`.
- Produces: `find_iterm_app()`, `build_workspace_attach_spec()`, and `launch_workspace()` returning the visible application name.

- [ ] **Step 1: Write failing launcher tests**

Add imports and tests:

```python
from harness.launcher import build_workspace_attach_spec, find_iterm_app, launch_workspace


class WorkspaceLauncherTests(unittest.TestCase):
    def test_iterm_attach_uses_tmux_control_mode(self):
        spec = build_workspace_attach_spec(
            "harness-demo-12345678", Path("/opt/homebrew/bin/tmux"), use_iterm=True
        )
        self.assertEqual(spec.argv[:2], ("osascript", "-e"))
        self.assertIn("tell application \"iTerm2\"", spec.argv[2])
        self.assertIn("tmux -CC attach -t harness-demo-12345678", spec.argv[2])

    def test_terminal_fallback_uses_standard_tmux_attach(self):
        spec = build_workspace_attach_spec(
            "harness-demo-12345678", Path("/opt/homebrew/bin/tmux"), use_iterm=False
        )
        self.assertIn("tell application \"Terminal\"", spec.argv[2])
        self.assertIn("tmux attach -t harness-demo-12345678", spec.argv[2])
        self.assertNotIn("-CC", spec.argv[2])

    def test_find_iterm_checks_system_and_user_applications(self):
        existing = {Path("/Users/me/Applications/iTerm.app")}
        found = find_iterm_app(
            home=Path("/Users/me"),
            is_dir=lambda path: path in existing,
        )
        self.assertEqual(found, Path("/Users/me/Applications/iTerm.app"))
```

- [ ] **Step 2: Run the launcher tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_harness.WorkspaceLauncherTests -v
```

Expected: import errors for the workspace launcher API.

- [ ] **Step 3: Implement iTerm2 detection and attach launch specs**

Add to `harness/launcher.py`:

```python
from collections.abc import Callable


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
        command = f"{binary} -CC attach -t {session_name}"
        script = (
            'tell application "iTerm2"\n'
            "activate\n"
            "set newWindow to (create window with default profile)\n"
            f'tell current session of newWindow to write text "{command}"\n'
            "end tell"
        )
    else:
        command = f"{binary} attach -t {session_name}"
        script = (
            'tell application "Terminal"\n'
            "activate\n"
            f'do script "{command}"\n'
            "end tell"
        )
    return LaunchSpec(("osascript", "-e", script))


def launch_workspace(session_name: str, tmux_path: Path) -> str:
    application = "iTerm2" if find_iterm_app() else "Terminal"
    spec = build_workspace_attach_spec(
        session_name, tmux_path, use_iterm=application == "iTerm2"
    )
    try:
        subprocess.Popen(spec.argv)
    except OSError as error:
        raise LaunchError(f"Could not open terminal workspace: {error}") from error
    return application
```

Also add `import re`. Keep `build_launch_spec()` and `launch_agent()` unchanged except for their shared validator from Task 1.

- [ ] **Step 4: Run launcher and full tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_harness.WorkspaceLauncherTests -v
.venv/bin/python -m unittest tests.test_harness -q
```

Expected: all launcher tests pass; existing macOS and Windows single-terminal specs remain unchanged.

- [ ] **Step 5: Commit Task 3**

```bash
git add harness/launcher.py tests/test_harness.py
git commit -m "Open tmux workspaces in iTerm2"
```

---

### Task 4: Project-Level Workspace Controls

**Files:**
- Modify: `app.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: `collect_workspace_entries()`, `tmux_available()`, `workspace_exists()`, `start_workspace()`, `stop_workspace()`, and `launch_workspace()`.
- Produces: visible **Open Workspace** / **Show Workspace** and conditional **Stop Workspace** controls.

- [ ] **Step 1: Write failing pure-state tests before changing Tk widgets**

Add a pure helper to the intended imports and write tests first:

```python
from app import workspace_control_state


class WorkspaceControlStateTests(unittest.TestCase):
    def test_disabled_without_project_or_valid_assignments(self):
        self.assertEqual(workspace_control_state(False, False, False), ("Open Workspace", False, False))
        self.assertEqual(workspace_control_state(True, False, False), ("Open Workspace", False, False))

    def test_open_and_show_states(self):
        self.assertEqual(workspace_control_state(True, True, False), ("Open Workspace", True, False))
        self.assertEqual(workspace_control_state(True, True, True), ("Show Workspace", True, True))
```

- [ ] **Step 2: Run the state tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_harness.WorkspaceControlStateTests -v
```

Expected: import error for `workspace_control_state`.

- [ ] **Step 3: Add the pure state helper and header controls**

Add to `app.py`:

```python
def workspace_control_state(
    has_project: bool,
    has_entries: bool,
    session_exists: bool,
) -> tuple[str, bool, bool]:
    return (
        "Show Workspace" if session_exists else "Open Workspace",
        has_project and has_entries,
        session_exists,
    )
```

In `_build_workspace()`, place `Open Workspace` beside `Set Root` using `Action.TButton`. Create `Stop Workspace` using `Ghost.TButton`; call `grid_remove()` initially so it does not consume header space until a managed session exists.

Add these methods to `HarnessDashboard`:

```python
def _workspace_selection(self):
    if self.project_root is None:
        return None
    return collect_workspace_entries(self.project_root, self.assignments, self.agents)

def _refresh_workspace_controls(self) -> None:
    selection = self._workspace_selection()
    has_entries = bool(selection and selection.entries)
    exists = False
    if self.project_root is not None and tmux_available():
        try:
            exists = workspace_exists(self.project_root)
        except WorkspaceError:
            exists = False
    label, enabled, show_stop = workspace_control_state(
        self.project_root is not None, has_entries, exists
    )
    self.workspace_button.configure(text=label, state="normal" if enabled else "disabled")
    if show_stop:
        self.stop_workspace_button.grid()
    else:
        self.stop_workspace_button.grid_remove()

def _open_workspace(self) -> None:
    selection = self._workspace_selection()
    if self.project_root is None or selection is None or not selection.entries:
        self.status_text.set("Assign at least one available agent first")
        return
    if not tmux_available():
        messagebox.showerror(
            "tmux is required",
            "Install tmux with 'brew install tmux', then reopen the workspace. Harness will not install it automatically.",
            parent=self.root,
        )
        return
    try:
        result = start_workspace(self.project_root, selection.entries)
        application = launch_workspace(result.session_name, result.tmux_path)
    except (WorkspaceError, LaunchError) as error:
        messagebox.showerror("Cannot open workspace", str(error), parent=self.root)
        return
    verb = "Reopened" if result.reused else "Opened"
    skipped = f"; skipped {len(selection.skipped)}" if selection.skipped else ""
    self.status_text.set(f"{verb} {result.pane_count} terminals in {application}{skipped}")
    if selection.skipped:
        messagebox.showwarning(
            "Some folders were skipped",
            "\n".join(selection.skipped),
            parent=self.root,
        )
    self._refresh_workspace_controls()

def _stop_workspace(self) -> None:
    if self.project_root is None:
        return
    if not messagebox.askyesno(
        "Stop workspace",
        "Stop every Agent terminal in this project workspace?",
        parent=self.root,
    ):
        return
    try:
        stop_workspace(self.project_root)
    except WorkspaceError as error:
        messagebox.showerror("Cannot stop workspace", str(error), parent=self.root)
        return
    self.status_text.set("Stopped terminal workspace")
    self._refresh_workspace_controls()
```

Call `_refresh_workspace_controls()` after loading a root, assigning, unassigning, deleting/reloading Agents, opening a workspace, and stopping one. Keep `_open_terminal()` unchanged.

- [ ] **Step 4: Run unit tests and a source GUI smoke test**

Run:

```bash
.venv/bin/python -m unittest tests.test_harness -q
.venv/bin/python -m compileall -q app.py harness tests
```

Then launch `app.py`, load a temporary project, and verify:

- **Open Workspace** is disabled before assignments.
- assigning an Agent enables it.
- a detected session changes it to **Show Workspace** and reveals **Stop Workspace**.
- **Open Terminal** still launches only the selected folder.

- [ ] **Step 5: Commit Task 4**

```bash
git add app.py tests/test_harness.py
git commit -m "Add adaptive workspace controls"
```

---

### Task 5: User Guidance, Packaged Build, and Real tmux Verification

**Files:**
- Modify: `README.md`
- Verify: `scripts/build.py`
- Verify: `dist/HarnessDashboard.app`

**Interfaces:**
- Consumes: the completed workspace UI and launcher.
- Produces: installation guidance and fresh macOS runtime evidence.

- [ ] **Step 1: Document the two launch modes and prerequisites**

Add a `Terminal Workspace` section to `README.md` stating:

```markdown
## Terminal Workspace

`Open Terminal`은 선택한 폴더의 Agent 하나만 엽니다. `Open Workspace`는 현재 프로젝트에 정상 배치된 Agent를 모두 하나의 tmux 세션으로 실행하고 iTerm2에서 균등한 `tiled` 배치로 보여줍니다. 기존 세션이 있으면 Agent를 중복 실행하지 않고 `Show Workspace`로 다시 연결합니다.

macOS 워크스페이스 기능에는 tmux가 필요하며 iTerm2 사용을 권장합니다. Harness는 두 프로그램을 자동 설치하지 않습니다. iTerm2가 없으면 기본 Terminal 앱으로 열립니다.

```bash
brew install tmux
```

`Stop Workspace`는 현재 프로젝트의 Harness tmux 세션과 그 안의 Agent를 모두 종료합니다.
```

- [ ] **Step 2: Run all automated verification**

Run:

```bash
.venv/bin/python -m unittest tests.test_harness -q
.venv/bin/python -m compileall -q app.py harness tests
.venv/bin/python scripts/build.py
test -x dist/HarnessDashboard.app/Contents/MacOS/HarnessDashboard
```

Expected: tests pass, compilation is silent, PyInstaller succeeds, and the packaged executable exists.

- [ ] **Step 3: Run isolated tmux layout smoke cases**

Use a dedicated tmux server socket so no personal sessions are touched. For each count in `1 2 3 4 6 10`, create short-lived shell panes through the new controller, inspect `tmux list-panes -F '#{pane_id} #{pane_width} #{pane_height} #{pane_title}'`, verify all titles and non-zero sizes, then kill only that dedicated test server.

Expected: each count creates the requested number of panes; 3 and higher use more than one row and column when the test window is large enough.

- [ ] **Step 4: Run iTerm2 and fallback smoke checks**

With iTerm2 installed, launch a two-pane workspace and verify one iTerm2 tmux-control workspace appears, closes without killing the tmux session, and reopens through **Show Workspace**. Temporarily force `find_iterm_app()` to return `None` in a test patch and verify the generated fallback spec targets Terminal without opening a second Agent session.

- [ ] **Step 5: Commit Task 5**

```bash
git add README.md
git commit -m "Document adaptive terminal workspaces"
```

- [ ] **Step 6: Request code review and fix Critical or Important findings**

Use `superpowers:requesting-code-review` against all commits introduced by this plan. Rerun the complete automated verification after any fix.
