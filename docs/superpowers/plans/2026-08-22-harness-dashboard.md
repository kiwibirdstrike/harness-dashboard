# AI Harness Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one desktop codebase that works fully on macOS first, stores per-folder agent assignments, launches the assigned CLI, builds as a macOS app, and then adds the small Windows-specific launch and release-build path.

**Architecture:** A Tkinter entry point owns only UI state. Three standard-library modules provide deterministic directory scanning, atomic JSON persistence, and platform-specific launch specifications. PyInstaller packages the same source on native macOS and Windows runners.

**Tech Stack:** Python 3.10+, Tkinter, `unittest`, PyInstaller 6.22.2, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-22-harness-dashboard-design.md`

## Global Constraints

- Keep one source tree for macOS and Windows.
- Finish and verify macOS behavior before adding Windows packaging.
- Store project settings only in `<project>/.harness.json`.
- Runtime code uses only the Python standard library.
- Supported agents are exactly Codex, Claude, and Gemini in the MVP.
- Do not add session monitoring, orchestration, prompt editing, installers, code signing, notarization, or automatic updates.

---

### Task 1: Directory scanning and configuration persistence

**Files:**
- Create: `.gitignore`
- Create: `harness/__init__.py`
- Create: `harness/scanner.py`
- Create: `harness/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_harness.py`

**Interfaces:**
- Produces: `FolderNode(path: Path, children: tuple[FolderNode, ...])`
- Produces: `scan_folders(root: Path) -> FolderNode`
- Produces: `ConfigError`
- Produces: `load_assignments(root: Path) -> dict[str, str]`
- Produces: `save_assignments(root: Path, assignments: Mapping[str, str]) -> None`

- [ ] **Step 1: Initialize the repository and ignore generated files**

Run `git init`, then create `.gitignore` with:

```gitignore
__pycache__/
*.py[cod]
.DS_Store
.venv/
build/
dist/
*.spec
```

- [ ] **Step 2: Write failing scanner tests**

Add tests that create a temporary tree and assert that ordinary folders are sorted, the root is represented, and hidden/build/cache/symlink directories are absent:

```python
class ScannerTests(unittest.TestCase):
    def test_scan_returns_sorted_visible_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "beta").mkdir()
            (root / "alpha" / "nested").mkdir(parents=True)
            (root / ".hidden").mkdir()
            (root / "node_modules").mkdir()

            tree = scan_folders(root)

            self.assertEqual(tree.path, root.resolve())
            self.assertEqual([child.path.name for child in tree.children], ["alpha", "beta"])
            self.assertEqual(tree.children[0].children[0].path.name, "nested")

    def test_scan_does_not_follow_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            link = root / "linked"
            link.symlink_to(target, target_is_directory=True)

            tree = scan_folders(root)

            self.assertEqual([child.path.name for child in tree.children], ["target"])
```

- [ ] **Step 3: Run the scanner tests and verify RED**

Run: `python3 -m unittest tests.test_harness.ScannerTests -v`

Expected: import failure because `harness.scanner` does not exist.

- [ ] **Step 4: Implement the minimum scanner**

Use a frozen dataclass and a single recursive function. Skip names beginning with `.` plus `node_modules`, `__pycache__`, `venv`, `dist`, and `build`. Catch `OSError` around child enumeration and return the node with no children.

```python
@dataclass(frozen=True)
class FolderNode:
    path: Path
    children: tuple["FolderNode", ...] = ()


def scan_folders(root: Path) -> FolderNode:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    return _scan(root)
```

- [ ] **Step 5: Run scanner tests and verify GREEN**

Run: `python3 -m unittest tests.test_harness.ScannerTests -v`

Expected: 2 tests pass.

- [ ] **Step 6: Write failing configuration tests**

Add tests for missing configuration, valid round-trip, unknown-agent filtering, malformed JSON, and protection against overwriting malformed JSON:

```python
class ConfigTests(unittest.TestCase):
    def test_assignments_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = {"research": "Gemini", "src": "Codex"}
            save_assignments(root, expected)
            self.assertEqual(load_assignments(root), expected)

    def test_invalid_json_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".harness.json"
            config.write_text("{broken", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_assignments(root)
            self.assertEqual(config.read_text(encoding="utf-8"), "{broken")
```

- [ ] **Step 7: Run configuration tests and verify RED**

Run: `python3 -m unittest tests.test_harness.ConfigTests -v`

Expected: import failure because `harness.config` does not exist.

- [ ] **Step 8: Implement atomic JSON persistence**

Implement version `1` JSON. Accept only a dictionary of string relative paths mapped to `Codex`, `Claude`, or `Gemini`. Ignore unknown agent values when loading. Write a temporary file in the project root, flush it, then replace `.harness.json` with `os.replace`; remove the temporary file on failure.

- [ ] **Step 9: Run Task 1 verification**

Run: `python3 -m unittest tests.test_harness -v`

Expected: all scanner and configuration tests pass.

- [ ] **Step 10: Commit Task 1**

```text
Preserve project assignments without external services

Constraint: Runtime must remain standard-library only
Confidence: high
Scope-risk: narrow
Tested: python3 -m unittest tests.test_harness -v
```

---

### Task 2: Cross-platform terminal launch specification

**Files:**
- Create: `harness/launcher.py`
- Modify: `tests/test_harness.py`

**Interfaces:**
- Produces: `AGENT_COMMANDS: dict[str, str]`
- Produces: `LaunchError`
- Produces: `LaunchSpec(argv: tuple[str, ...], cwd: Path | None, creationflags: int)`
- Produces: `build_launch_spec(folder: Path, agent: str, system: str | None = None) -> LaunchSpec`
- Produces: `launch_agent(folder: Path, agent: str) -> None`

- [ ] **Step 1: Write failing launcher tests**

```python
class LauncherTests(unittest.TestCase):
    def test_macos_spec_quotes_shell_path_and_escapes_applescript(self):
        folder = Path('/tmp/Client\'s "Project"')
        spec = build_launch_spec(folder, "Codex", system="Darwin")
        self.assertEqual(spec.argv[:2], ("osascript", "-e"))
        self.assertIn("codex", spec.argv[2])
        self.assertIn("cd ", spec.argv[2])
        self.assertIn("\\\"Project\\\"", spec.argv[2])

    def test_windows_spec_uses_working_directory_without_path_concatenation(self):
        folder = Path(r"C:\\Users\\A Person\\Project")
        spec = build_launch_spec(folder, "Claude", system="Windows")
        self.assertEqual(spec.argv, ("cmd.exe", "/k", "claude"))
        self.assertEqual(spec.cwd, folder)

    def test_unknown_agent_and_platform_are_rejected(self):
        with self.assertRaises(LaunchError):
            build_launch_spec(Path("/tmp"), "Other", system="Darwin")
        with self.assertRaises(LaunchError):
            build_launch_spec(Path("/tmp"), "Codex", system="Linux")
```

- [ ] **Step 2: Run launcher tests and verify RED**

Run: `python3 -m unittest tests.test_harness.LauncherTests -v`

Expected: import failure because `harness.launcher` does not exist.

- [ ] **Step 3: Implement launch specs**

Use `shlex.quote` for the macOS shell path, escape backslashes and double quotes before embedding the shell command in AppleScript, and use `subprocess.CREATE_NEW_CONSOLE` when available for Windows. Keep the agent commands fixed:

```python
AGENT_COMMANDS = {
    "Codex": "codex",
    "Claude": "claude",
    "Gemini": "gemini",
}
```

`launch_agent` validates that the folder still exists, builds the spec for `platform.system()`, and calls `subprocess.Popen` with the spec fields.

- [ ] **Step 4: Run launcher and full core tests**

Run: `python3 -m unittest tests.test_harness -v`

Expected: all tests pass without opening an external terminal.

- [ ] **Step 5: Commit Task 2**

```text
Launch each agent from the folder it owns

Constraint: macOS ships first while Windows shares the same source
Rejected: Separate platform applications | Shared behavior would drift
Confidence: high
Scope-risk: narrow
Tested: python3 -m unittest tests.test_harness -v
```

---

### Task 3: Tkinter dashboard

**Files:**
- Create: `app.py`
- Modify: `tests/test_harness.py`

**Interfaces:**
- Consumes: `scan_folders`, `load_assignments`, `save_assignments`, `AGENT_COMMANDS`, `launch_agent`
- Produces: `HarnessDashboard(tk.Tk)` and `main() -> None`

- [ ] **Step 1: Add one failing UI-independent path test**

Add a test for the relative-path key used by the UI:

```python
class AppPathTests(unittest.TestCase):
    def test_root_and_child_assignment_keys(self):
        root = Path("/project")
        self.assertEqual(assignment_key(root, root), ".")
        self.assertEqual(assignment_key(root, root / "src"), "src")
```

Keep `assignment_key(root, folder) -> str` at module level so this behavior is testable without creating a graphical window.

- [ ] **Step 2: Run the app path test and verify RED**

Run: `python3 -m unittest tests.test_harness.AppPathTests -v`

Expected: import failure because `app.py` or `assignment_key` does not exist.

- [ ] **Step 3: Implement the dashboard**

Create one `ttk` window with:

- an “Open Folder” button and project-path label;
- a `ttk.Treeview` populated recursively from `FolderNode`;
- a details panel showing the selected path;
- a readonly agent `Combobox` containing `Unassigned`, `Codex`, `Claude`, and `Gemini`;
- an “Open Terminal” button disabled while unassigned.

On folder selection, load the current assignment into the combobox. On combobox selection, update the in-memory mapping and call `save_assignments`. On launch, call `launch_agent`. Catch `ConfigError`, `LaunchError`, `OSError`, and `ValueError` at the UI boundary and show `messagebox.showerror`.

- [ ] **Step 4: Run automated verification**

Run: `python3 -m unittest tests.test_harness -v`

Run: `python3 -m compileall -q app.py harness tests`

Expected: both commands exit 0.

- [ ] **Step 5: Run the macOS source smoke check**

Run: `python3 app.py`

Manually verify: the window opens; a folder can be selected; tree items appear; assigning Codex writes `.harness.json`; reopening the project restores Codex; “Open Terminal” starts Codex in the selected folder. Close the test terminal and app afterward.

- [ ] **Step 6: Commit Task 3**

```text
Make local agent workspaces visible and launchable

Constraint: The first complete user flow must work on macOS
Confidence: medium
Scope-risk: moderate
Tested: unittest, compileall, macOS source smoke check
```

---

### Task 4: macOS app build and documentation

**Files:**
- Create: `scripts/build.py`
- Create: `requirements-build.txt`
- Create: `README.md`

**Interfaces:**
- Produces: `python3 scripts/build.py` command
- Produces: `dist/HarnessDashboard.app` on macOS

- [ ] **Step 1: Add a failing build-command test**

Expose `build_command(system: str | None = None) -> list[str]` from `scripts/build.py` and test that Darwin uses `--windowed`, `--onedir`, `--name HarnessDashboard`, and `app.py`.

- [ ] **Step 2: Run the build-command test and verify RED**

Run: `python3 -m unittest tests.test_harness.BuildScriptTests -v`

Expected: import failure because `scripts.build` does not exist.

- [ ] **Step 3: Implement the build script and dependency file**

Pin `PyInstaller==6.22.2` in `requirements-build.txt`. The script runs:

```python
[
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--windowed", "--onedir",
    "--name", "HarnessDashboard", "app.py",
]
```

- [ ] **Step 4: Write concise usage documentation**

Document source execution, agent CLI prerequisites, local build commands, `.harness.json`, current macOS-first status, unsigned-app warning, and the later Windows release path.

- [ ] **Step 5: Build and inspect the macOS app**

Run: `python3 -m pip install -r requirements-build.txt`

Run: `python3 scripts/build.py`

Expected: `dist/HarnessDashboard.app` exists.

Open the bundle and repeat the Task 3 smoke check.

- [ ] **Step 6: Commit Task 4**

```text
Let Mac users run the dashboard without a Python setup

Constraint: Unsigned local distribution through GitHub
Rejected: One-file app bundle | PyInstaller documents slower startup and weaker app-bundle behavior
Confidence: medium
Scope-risk: moderate
Tested: unittest, compileall, PyInstaller build, bundled-app smoke check
```

---

### Task 5: Windows verification and GitHub release automation

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: the same `app.py`, `harness/`, `tests/`, and `scripts/build.py`
- Produces: zipped Apple Silicon macOS `.app` and Windows x64 application directory for each `v*` tag

- [ ] **Step 1: Add the release workflow**

Use a matrix containing `macos-15` and `windows-latest`. Each job checks out the repository, installs Python 3.10, installs `requirements-build.txt`, runs `python -m unittest tests.test_harness -v`, runs `python scripts/build.py`, and archives the native result. A release job attaches both archives to the version tag.

- [ ] **Step 2: Validate the workflow locally**

Check that YAML parses and that every command uses syntax valid in the selected runner shell. Verify the artifact paths separately for `.app` and Windows `dist/HarnessDashboard/`.

- [ ] **Step 3: Push a test tag and inspect both jobs**

Push a pre-release tag such as `v0.1.0`. Confirm that both platform test/build jobs pass and both archives appear on the GitHub Release.

- [ ] **Step 4: Run the Windows smoke check**

On Windows, download the release archive, open `HarnessDashboard.exe`, select a project, assign an installed agent, restart the app to verify persistence, and confirm a new console opens in the selected folder.

- [ ] **Step 5: Update support status and commit**

Only after the Windows smoke check passes, change the README status from “macOS verified, Windows code included” to “macOS and Windows verified.”

```text
Publish one verified build for each desktop platform

Constraint: PyInstaller must build separately on each operating system
Confidence: medium
Scope-risk: moderate
Tested: GitHub Actions macOS and Windows jobs, release downloads, platform smoke checks
```
