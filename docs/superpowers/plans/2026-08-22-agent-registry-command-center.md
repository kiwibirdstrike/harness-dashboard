# Agent Registry and Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed agents with a user-managed global registry and deliver the approved dark Command Center with image-backed Agent cards, Settings management, click assignment, and internal drag-and-drop assignment.

**Architecture:** A new `AgentRegistry` owns global agent data and copied PNG images. Project configuration migrates display-name assignments to stable IDs, while the launcher receives validated command text from the resolved Agent. Tkinter UI responsibilities split into the main coordinator, a Settings modal, and reusable Agent-card/drag widgets.

**Tech Stack:** Python 3.10+, Tkinter/Ttk, Python standard library, `unittest`, PyInstaller 6.22.2

**Spec:** `docs/superpowers/specs/2026-08-22-agent-registry-ui-design.md`

## Global Constraints

- Do not detect installed CLIs, subscriptions, accounts, or login state.
- Keep one user-managed Agent Registry shared by all projects on the computer.
- Store only stable Agent IDs in project configuration version 2.
- Accept optional PNG images only; do not add Pillow or another runtime dependency.
- Keep Tkinter for this iteration and implement only internal Agent-card drag and drop.
- Preserve existing version 1 Codex, Claude, and Gemini project assignments through migration.
- Keep code signing, notarization, installers, automatic updates, external file drag and drop, theme editing, and plugin systems out of scope.

---

### Task 1: Global Agent Registry and image ownership

**Files:**
- Create: `harness/agent_registry.py`
- Modify: `tests/test_harness.py`

**Interfaces:**
- Produces: `Agent(id: str, name: str, command: str, image: str | None, color: str)`
- Produces: `RegistryError`
- Produces: `app_data_dir(system: str | None = None, environ: Mapping[str, str] | None = None, home: Path | None = None) -> Path`
- Produces: `AgentRegistry(root: Path | None = None)`
- Produces: `AgentRegistry.load() -> list[Agent]`
- Produces: `AgentRegistry.add(name: str, command: str, color: str, image_source: Path | None = None) -> Agent`
- Produces: `AgentRegistry.update(agent_id: str, name: str, command: str, color: str, image_source: Path | None = None, remove_image: bool = False) -> Agent`
- Produces: `AgentRegistry.delete(agent_id: str) -> None`

- [ ] **Step 1: Write failing data-location and starter tests**

Add imports for `AgentRegistry`, `RegistryError`, and `app_data_dir`, then add:

```python
class AgentRegistryTests(unittest.TestCase):
    def test_app_data_dir_uses_native_locations(self):
        home = Path("/Users/tester")
        self.assertEqual(
            app_data_dir(system="Darwin", home=home),
            home / "Library" / "Application Support" / "HarnessDashboard",
        )
        self.assertEqual(
            app_data_dir(
                system="Windows",
                environ={"APPDATA": r"C:\Users\tester\AppData\Roaming"},
                home=Path(r"C:\Users\tester"),
            ),
            Path(r"C:\Users\tester\AppData\Roaming") / "HarnessDashboard",
        )

    def test_missing_registry_creates_removable_starter_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistry(Path(tmp))
            agents = registry.load()
            self.assertEqual([agent.name for agent in agents], ["Codex", "Claude", "Gemini"])
            registry.delete(agents[0].id)
            self.assertEqual([agent.name for agent in registry.load()], ["Claude", "Gemini"])

    def test_invalid_registry_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "agents.json"
            config.write_text("{broken", encoding="utf-8")
            with self.assertRaises(RegistryError):
                AgentRegistry(root).load()
            self.assertEqual(config.read_text(encoding="utf-8"), "{broken")
```

- [ ] **Step 2: Run registry tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_harness.AgentRegistryTests -v`

Expected: import failure because `harness.agent_registry` does not exist.

- [ ] **Step 3: Implement the Agent model, validation, paths, and atomic store**

Create a frozen dataclass. `AgentRegistry.load()` creates three starter Agents only when `agents.json` does not exist. Generate IDs with `str(uuid.uuid4())`. Validate names with `name.strip()`, validate commands with this exact helper, and restrict colors to the declared palette:

```python
ACCENT_COLORS = (
    "#7C3AED", "#0EA5E9", "#D97706", "#16A34A", "#DC2626", "#DB2777"
)


def validate_command(command: str) -> str:
    command = command.strip()
    if not command or "\n" in command or "\r" in command or "\0" in command:
        raise RegistryError("Command must be one line")
    return command
```

Store this shape atomically in `<root>/agents.json`:

```json
{"version": 1, "agents": [{"id": "...", "name": "Codex", "command": "codex", "image": null, "color": "#7C3AED"}]}
```

- [ ] **Step 4: Run starter tests and verify GREEN**

Run: `.venv/bin/python -m unittest tests.test_harness.AgentRegistryTests -v`

Expected: the 3 new tests pass.

- [ ] **Step 5: Write failing CRUD, validation, and PNG ownership tests**

Add tests that use a real one-pixel PNG byte sequence:

```python
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_add_update_delete_and_image_copy(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "avatar.png"
        source.write_bytes(PNG_1X1)
        registry = AgentRegistry(root / "data")
        registry.load()
        added = registry.add("My Agent", "agent --pro", "#0EA5E9", source)
        copied = registry.root / added.image
        self.assertTrue(copied.is_file())
        source.unlink()
        updated = registry.update(added.id, "Renamed", "agent --fast", "#16A34A")
        self.assertEqual(updated.name, "Renamed")
        registry.delete(added.id)
        self.assertFalse(copied.exists())


def test_invalid_command_and_non_png_are_rejected_without_mutation(self):
    with tempfile.TemporaryDirectory() as tmp:
        registry = AgentRegistry(Path(tmp))
        before = registry.load()
        bad_image = Path(tmp) / "avatar.jpg"
        bad_image.write_bytes(b"not a png")
        with self.assertRaises(RegistryError):
            registry.add("Bad", "bad\ncommand", "#7C3AED", bad_image)
        self.assertEqual(registry.load(), before)
```

- [ ] **Step 6: Run new registry tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_harness.AgentRegistryTests -v`

Expected: failures because CRUD and image ownership are not implemented.

- [ ] **Step 7: Implement minimal CRUD and copied-image cleanup**

Require `.png` suffix and the eight-byte PNG signature before copying. Copy to a temporary file under `<root>/images/`, replace the final image, atomically save the registry, then remove superseded images. If any step fails, delete only the newly created temporary/final image and leave the previous registry and previous image unchanged.

- [ ] **Step 8: Run Task 1 verification**

Run: `.venv/bin/python -m unittest tests.test_harness.AgentRegistryTests -v`

Expected: all Agent Registry tests pass.

- [ ] **Step 9: Commit Task 1**

```text
Let users define the agents they actually own

Constraint: Subscription state cannot be inferred from a CLI installation
Rejected: Automatic agent detection | It gives false confidence about access
Confidence: high
Scope-risk: moderate
Tested: AgentRegistry unittest class
```

---

### Task 2: Stable project assignments and configured launch commands

**Files:**
- Modify: `harness/config.py`
- Modify: `harness/launcher.py`
- Modify: `harness/__init__.py`
- Modify: `tests/test_harness.py`

**Interfaces:**
- Consumes: `Agent` and the registry name-to-ID mapping
- Produces: `load_assignments(root: Path, legacy_name_to_id: Mapping[str, str] | None = None) -> dict[str, str]`
- Produces: `save_assignments(root: Path, assignments: Mapping[str, str]) -> None` writing version 2
- Produces: `build_launch_spec(folder: Path, command: str, system: str | None = None) -> LaunchSpec`
- Produces: `launch_agent(folder: Path, command: str) -> None`

- [ ] **Step 1: Write failing version migration tests**

Replace the old test that filtered unknown agent names, because version 2 must preserve missing IDs. Add:

```python
def test_version_one_names_migrate_to_ids_and_preserve_unknown_values(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".harness.json").write_text(
            '{"version": 1, "assignments": {"src": "Codex", "docs": "Private"}}',
            encoding="utf-8",
        )
        assignments = load_assignments(root, {"Codex": "codex-id"})
        self.assertEqual(assignments, {"src": "codex-id", "docs": "Private"})
        save_assignments(root, assignments)
        saved = json.loads((root / ".harness.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["version"], 2)


def test_version_two_preserves_missing_agent_ids(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".harness.json").write_text(
            '{"version": 2, "assignments": {"src": "deleted-agent-id"}}',
            encoding="utf-8",
        )
        self.assertEqual(load_assignments(root), {"src": "deleted-agent-id"})
```

- [ ] **Step 2: Run migration tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_harness.ConfigTests -v`

Expected: version 1 call rejects the extra mapping argument or version 2 is unsupported.

- [ ] **Step 3: Implement v1 read migration and v2 writes**

Accept versions 1 and 2. For version 1, replace each value with `legacy_name_to_id.get(value, value)`. Do not filter values against the live registry. Save only version 2. Retain relative-path validation.

- [ ] **Step 4: Write failing configured-command launcher tests**

Replace fixed-agent assertions with:

```python
def test_macos_spec_runs_configured_command_with_arguments(self):
    spec = build_launch_spec(Path("/tmp/Project"), "claude --model opus", system="Darwin")
    self.assertIn("claude --model opus", spec.argv[2])


def test_windows_spec_runs_configured_command_in_working_directory(self):
    folder = Path(r"C:\Users\A Person\Project")
    spec = build_launch_spec(folder, "codex --full-auto", system="Windows")
    self.assertEqual(spec.argv, ("cmd.exe", "/k", "codex --full-auto"))
    self.assertEqual(spec.cwd, folder)


def test_control_characters_are_rejected(self):
    with self.assertRaises(LaunchError):
        build_launch_spec(Path("/tmp"), "codex\nwhoami", system="Darwin")
```

- [ ] **Step 5: Run launcher tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_harness.LauncherTests -v`

Expected: fixed agent lookup rejects configured command text.

- [ ] **Step 6: Make the launcher command-driven**

Remove `AGENT_COMMANDS` from `harness/__init__.py`. Validate command text independently in `launcher.py` so corrupt registry data cannot bypass the boundary. Preserve folder quoting, AppleScript escaping, Windows working directory, and missing-folder checks.

- [ ] **Step 7: Run Task 2 verification**

Run: `.venv/bin/python -m unittest tests.test_harness.ConfigTests tests.test_harness.LauncherTests -v`

Expected: migration and configured-command tests pass.

- [ ] **Step 8: Commit Task 2**

```text
Keep folder assignments stable as agent names evolve

Constraint: Existing version 1 projects must not lose assignments
Confidence: high
Scope-risk: moderate
Tested: ConfigTests and LauncherTests
```

---

### Task 3: Agent cards and internal drag mechanics

**Files:**
- Create: `harness/widgets.py`
- Modify: `tests/test_harness.py`

**Interfaces:**
- Consumes: `Agent`
- Produces: `fallback_initial(name: str) -> str`
- Produces: `tree_row_at_pointer(tree: object, x_root: int, y_root: int) -> str`
- Produces: `AgentCard(tk.Canvas)` with `agent_id`, click callback, and drag-start callback
- Produces: `AgentDragController(root: tk.Misc, tree: ttk.Treeview, on_drop: Callable[[str, str], None])`

- [ ] **Step 1: Write failing pure widget-helper tests**

Add a fake Treeview boundary:

```python
class FakeTree:
    def winfo_rootx(self): return 100
    def winfo_rooty(self): return 200
    def identify_row(self, y): return "row-3" if y == 25 else ""


class WidgetHelperTests(unittest.TestCase):
    def test_fallback_initial_uses_first_visible_character(self):
        self.assertEqual(fallback_initial("  Claude"), "C")
        self.assertEqual(fallback_initial(""), "?")

    def test_tree_row_at_pointer_converts_screen_to_widget_coordinates(self):
        self.assertEqual(tree_row_at_pointer(FakeTree(), 130, 225), "row-3")
        self.assertEqual(tree_row_at_pointer(FakeTree(), 130, 260), "")
```

- [ ] **Step 2: Run helper tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_harness.WidgetHelperTests -v`

Expected: import failure because `harness.widgets` does not exist.

- [ ] **Step 3: Implement helper functions and a minimal AgentCard**

`AgentCard` is a Canvas with a colored left border, 36-pixel avatar, name, and command. Load copied PNGs through `tk.PhotoImage`; use `fallback_initial` if loading fails. Keep a reference to each PhotoImage on the widget to prevent garbage collection.

- [ ] **Step 4: Implement the drag controller**

Bind card press/motion/release. Create one borderless `Toplevel` ghost after pointer movement exceeds 5 pixels. On motion, use `tree_row_at_pointer`, set a `drag-target` Treeview tag on the identified item, and clear the previous target. On release, destroy the ghost, clear highlighting, and call `on_drop(agent_id, item_id)` only when a valid target exists. A simple click invokes the card click callback and never creates a ghost.

- [ ] **Step 5: Run Task 3 verification**

Run: `.venv/bin/python -m unittest tests.test_harness.WidgetHelperTests -v`

Run: `env PYTHONPYCACHEPREFIX=/tmp/harness-widget-pycache .venv/bin/python -m compileall -q harness/widgets.py`

Expected: helper tests and compilation pass.

- [ ] **Step 6: Commit Task 3**

```text
Make agent placement direct without a drag dependency

Constraint: Tkinter internal drag only
Rejected: tkinterdnd2 | External file dragging is out of scope
Confidence: medium
Scope-risk: moderate
Tested: WidgetHelperTests and compileall
```

---

### Task 4: Agent Settings management window

**Files:**
- Create: `harness/settings_window.py`
- Modify: `tests/test_harness.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `Agent`, and `ACCENT_COLORS`
- Produces: `AgentSettingsWindow(parent: tk.Misc, registry: AgentRegistry, on_change: Callable[[], None])`
- Produces: `validate_form(name: str, command: str, color: str) -> tuple[str, str, str]`

- [ ] **Step 1: Write failing form validation tests**

```python
class SettingsValidationTests(unittest.TestCase):
    def test_form_normalizes_valid_values(self):
        self.assertEqual(
            validate_form("  My Codex  ", " codex --fast ", "#7C3AED"),
            ("My Codex", "codex --fast", "#7C3AED"),
        )

    def test_form_rejects_missing_name_and_unknown_color(self):
        with self.assertRaises(RegistryError):
            validate_form(" ", "codex", "#7C3AED")
        with self.assertRaises(RegistryError):
            validate_form("Codex", "codex", "#000000")
```

- [ ] **Step 2: Run validation tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_harness.SettingsValidationTests -v`

Expected: import failure because `harness.settings_window` does not exist.

- [ ] **Step 3: Implement validation and Settings UI**

Build one modal `Toplevel` with an agent list on the left and a form on the right. Use `filedialog.askopenfilename(filetypes=[("PNG image", "*.png")])`. Provide New, Save, and Delete buttons; show Delete only for an existing Agent. Use `messagebox.askyesno` before delete and `messagebox.showerror` for `RegistryError`/`OSError`. After successful mutation, call `on_change()` and refresh the list while keeping the saved Agent selected.

- [ ] **Step 4: Add image preview fallback**

Load selected/copied PNG through `tk.PhotoImage`, reduce oversized images with integer `subsample`, and otherwise render the fallback initial in the selected accent color. A corrupt image displays the fallback and a single `messagebox.showwarning` when selected.

- [ ] **Step 5: Run Task 4 verification**

Run: `.venv/bin/python -m unittest tests.test_harness.SettingsValidationTests tests.test_harness.AgentRegistryTests -v`

Run: `env PYTHONPYCACHEPREFIX=/tmp/harness-settings-pycache .venv/bin/python -m compileall -q harness/settings_window.py`

Expected: tests and compilation pass.

- [ ] **Step 6: Commit Task 4**

```text
Put agent ownership under explicit user control

Constraint: Settings must never infer installation or subscription state
Confidence: medium
Scope-risk: moderate
Tested: SettingsValidationTests, AgentRegistryTests, compileall
```

---

### Task 5: Command Center integration and assignment interactions

**Files:**
- Modify: `app.py`
- Modify: `README.md`
- Modify: `tests/test_harness.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `AgentSettingsWindow`, `AgentCard`, `AgentDragController`, project assignment v2 functions, and command-driven launcher
- Produces: `resolve_agent_label(agent_id: str, agents: Mapping[str, Agent]) -> str`
- Produces: the approved three-pane Command Center UI

- [ ] **Step 1: Write failing missing-agent label and launch-state tests**

```python
class AppAgentTests(unittest.TestCase):
    def test_missing_agent_label_is_explicit(self):
        agent = Agent("known", "My Codex", "codex", None, "#7C3AED")
        self.assertEqual(resolve_agent_label("known", {"known": agent}), "My Codex")
        self.assertEqual(resolve_agent_label("deleted", {"known": agent}), "Missing agent")

    def test_launch_requires_resolved_agent_and_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = Agent("known", "My Codex", "codex", None, "#7C3AED")
            self.assertTrue(can_launch("known", {"known": agent}, Path(tmp)))
            self.assertFalse(can_launch("deleted", {"known": agent}, Path(tmp)))
```

- [ ] **Step 2: Run app-agent tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_harness.AppAgentTests -v`

Expected: function signatures still use the fixed agent model.

- [ ] **Step 3: Build the three-pane Command Center**

Replace the Combobox details view with:

- a 64-pixel dark navigation rail containing project and Settings actions;
- a center project header, Treeview with assignment badges, and selected-folder action panel;
- a 240-pixel Agent Dock with Manage and scrollable Agent cards.

Configure dark Ttk styles in one `_configure_styles()` method. Keep a minimum window size of 1100 by 680. Do not introduce a theme configuration file.

- [ ] **Step 4: Load and migrate Registry/project state together**

At startup, construct `AgentRegistry()` and load agents. When opening a project, pass `{agent.name: agent.id for agent in agents}` to `load_assignments`. Tree badges use `resolve_agent_label`; missing IDs remain assigned and render as `Missing agent`.

- [ ] **Step 5: Implement click assignment and removal**

Agent card click assigns its ID to the currently selected folder, saves version 2, updates the badge, and restores the previous state if saving fails. `Remove assignment` deletes only the selected folder key. Opening Settings and returning refreshes Dock cards and all visible badges.

- [ ] **Step 6: Wire drag assignment**

Create one `AgentDragController` for Dock cards. Map dropped Treeview item IDs through `self.item_paths`, then call the same assignment method used by click. Configure the `drag-target` tag with a violet background and clear it after every drop or cancel.

- [ ] **Step 7: Launch resolved commands**

Enable Open Terminal only when the selected folder exists and the assigned ID resolves. Pass `agent.command` to `launch_agent`. Missing IDs show the badge and never launch.

- [ ] **Step 8: Update user documentation**

Document Agent Settings fields, app-wide registry location, PNG-only images, click assignment, drag assignment, missing-agent behavior, and the absence of installation/subscription detection.

- [ ] **Step 9: Run Task 5 automated verification**

Run: `.venv/bin/python -m unittest tests.test_harness -v`

Run: `env PYTHONPYCACHEPREFIX=/tmp/harness-command-center-pycache .venv/bin/python -m compileall -q app.py harness scripts tests`

Expected: the full suite and compilation pass.

- [ ] **Step 10: Run macOS visual and interaction verification**

Run: `.venv/bin/python app.py`

Verify at 1100 by 680 and a larger size: add an Agent with PNG, edit its name, click-assign it, drag-assign it, remove assignment, delete it, observe `Missing agent` for a deliberately retained ID, and open a configured CLI. Confirm canceled drags make no change.

- [ ] **Step 11: Commit Task 5**

```text
Turn the dashboard into a visual agent command center

Constraint: Stay within Tkinter while preserving direct manipulation
Confidence: medium
Scope-risk: broad
Tested: full unittest suite, compileall, macOS interaction smoke check
```

---

### Task 6: Package and review the redesigned application

**Files:**
- Modify: `.github/workflows/release.yml` only if packaging paths changed
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: the complete Command Center source tree
- Produces: `dist/HarnessDashboard.app`

- [ ] **Step 1: Run final tests and whitespace validation**

Run: `.venv/bin/python -m unittest tests.test_harness -v`

Run: `git diff --check`

Expected: zero failures and no whitespace errors.

- [ ] **Step 2: Build the macOS app**

Run: `.venv/bin/python scripts/build.py`

Expected: PyInstaller exits 0 and `dist/HarnessDashboard.app/Contents/MacOS/HarnessDashboard` is executable.

- [ ] **Step 3: Launch the packaged app**

Run: `./dist/HarnessDashboard.app/Contents/MacOS/HarnessDashboard`

Repeat the Settings, click assignment, drag assignment, and terminal launch smoke checks from Task 5 using the packaged application.

- [ ] **Step 4: Request independent code review**

Review the complete feature range against `docs/superpowers/specs/2026-08-22-agent-registry-ui-design.md`. Fix all Critical and Important findings, rerun affected tests, and record any platform verification gap.

- [ ] **Step 5: Commit review fixes if needed**

Use a Lore-format commit that lists the exact review findings and fresh verification. If no files change, do not create an empty commit.
