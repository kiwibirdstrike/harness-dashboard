import base64
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import (
    assignment_key,
    can_launch,
    resolve_agent_label,
    tree_agent_label,
    workspace_control_state,
)
from harness.agent_registry import Agent, AgentRegistry, RegistryError, app_data_dir
from harness.config import ConfigError, load_assignments, save_assignments
from harness.launcher import (
    LaunchError,
    build_launch_spec,
    build_open_folder_spec,
    build_workspace_attach_spec,
    find_iterm_app,
    launch_workspace,
    validate_launch_command,
)
from harness.scanner import scan_folders
from harness.settings_window import validate_form
from harness.widgets import fallback_initial, tree_row_at_pointer
from harness.workspace import (
    WorkspaceEntry,
    WorkspaceError,
    collect_workspace_entries,
    find_tmux,
    start_workspace,
    stop_workspace,
    workspace_session_name,
)
from scripts.build import PROJECT_ROOT, build_command, build_environment


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
            self.assertEqual(
                [child.path.name for child in tree.children], ["alpha", "beta"]
            )
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


class ConfigTests(unittest.TestCase):
    def test_missing_config_returns_empty_assignments(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_assignments(Path(tmp)), {})

    def test_assignments_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = {"research": "agent-gemini", "src": "agent-codex"}

            save_assignments(root, expected)

            self.assertEqual(load_assignments(root), expected)
            self.assertIn('"version": 2', (root / ".harness.json").read_text(encoding="utf-8"))

    def test_version_one_names_migrate_to_ids_without_dropping_unknown_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness.json").write_text(
                '{"version": 1, "assignments": {"src": "Other", "docs": "Claude"}}',
                encoding="utf-8",
            )
            agents = [Agent("claude-id", "Claude", "claude", None, "#0EA5E9")]

            self.assertEqual(
                load_assignments(root, agents),
                {"src": "Other", "docs": "claude-id"},
            )

    def test_version_two_preserves_missing_agent_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness.json").write_text(
                '{"version": 2, "assignments": {"src": "deleted-agent-id"}}',
                encoding="utf-8",
            )

            self.assertEqual(load_assignments(root), {"src": "deleted-agent-id"})

    def test_invalid_json_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".harness.json"
            config.write_text("{broken", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_assignments(root)

            self.assertEqual(config.read_text(encoding="utf-8"), "{broken")


class AgentRegistryTests(unittest.TestCase):
    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    def test_app_data_dir_uses_native_locations(self):
        self.assertEqual(
            app_data_dir(system="Darwin", home=Path("/Users/test")),
            Path("/Users/test/Library/Application Support/HarnessDashboard"),
        )
        self.assertEqual(
            app_data_dir(
                system="Windows",
                environ={"APPDATA": r"C:\Users\test\AppData\Roaming"},
            ),
            Path(r"C:\Users\test\AppData\Roaming") / "HarnessDashboard",
        )

    def test_missing_registry_seeds_removable_starter_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistry(Path(tmp))

            agents = registry.load()

            self.assertEqual([agent.name for agent in agents], ["Codex", "Claude", "Gemini"])
            self.assertTrue(all(agent.description for agent in agents))
            self.assertTrue(all(agent.image and (registry.root / agent.image).is_file() for agent in agents))
            registry.delete(agents[0].id)
            self.assertEqual([agent.name for agent in registry.load()], ["Claude", "Gemini"])

    def test_version_one_registry_adds_starter_descriptions_and_icons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agents.json").write_text(
                '{"version": 1, "agents": [{"id": "codex-id", "name": "Codex", '
                '"command": "codex", "image": null, "color": "#7C3AED"}]}',
                encoding="utf-8",
            )

            agent = AgentRegistry(root).load()[0]

            self.assertIn("코딩", agent.description)
            self.assertTrue(agent.image and (root / agent.image).is_file())

    def test_invalid_json_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agents.json"
            path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(RegistryError):
                AgentRegistry(Path(tmp)).load()

            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_starter_icon_copy_failure_is_reported_as_registry_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "harness.agent_registry.shutil.copyfile",
                side_effect=OSError("disk unavailable"),
            ):
                with self.assertRaises(RegistryError):
                    AgentRegistry(Path(tmp)).load()

    def test_add_update_and_delete_own_the_agent_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "signature.png"
            source.write_bytes(self.PNG)
            registry = AgentRegistry(root / "data")
            registry.load()

            agent = registry.add("My Agent", "my-agent --local", source, "#16A34A")

            copied = registry.root / agent.image
            self.assertTrue(copied.is_file())
            source.unlink()
            updated = registry.update(agent.id, "Mine", "mine", None, "#DC2626")
            self.assertEqual((updated.name, updated.command, updated.image), ("Mine", "mine", None))
            self.assertFalse(copied.exists())
            registry.delete(agent.id)
            self.assertNotIn(agent.id, {item.id for item in registry.load()})

    def test_rejects_unsafe_commands_and_non_png_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = AgentRegistry(root / "data")
            registry.load()
            fake = root / "fake.png"
            fake.write_text("not png", encoding="utf-8")

            with self.assertRaises(RegistryError):
                registry.add("Bad", "bad\ncommand", None, "#7C3AED")
            with self.assertRaises(RegistryError):
                registry.add("Bad", "bad", fake, "#7C3AED")

    def test_failed_update_does_not_replace_the_previous_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.png"
            second = root / "second.png"
            first.write_bytes(self.PNG)
            second.write_bytes(self.PNG + b"replacement")
            registry = AgentRegistry(root / "data")
            registry.load()
            agent = registry.add("Mine", "mine", first, "#7C3AED")
            copied = registry.root / agent.image
            original = copied.read_bytes()

            with mock.patch.object(registry, "_save", side_effect=RegistryError("disk full")):
                with self.assertRaises(RegistryError):
                    registry.update(agent.id, "Mine", "mine", second, "#7C3AED")

            self.assertEqual(copied.read_bytes(), original)


class LauncherTests(unittest.TestCase):
    def test_macos_spec_quotes_shell_path_and_escapes_applescript(self):
        folder = Path('/tmp/Client\'s "Project"')

        spec = build_launch_spec(folder, "codex --profile local", system="Darwin")

        self.assertEqual(spec.argv[:2], ("osascript", "-e"))
        self.assertIn("codex", spec.argv[2])
        self.assertIn("cd ", spec.argv[2])
        self.assertIn('\\"Project\\"', spec.argv[2])

    def test_windows_spec_uses_working_directory_without_path_concatenation(self):
        folder = Path(r"C:\Users\A Person\Project")

        spec = build_launch_spec(folder, "claude --resume", system="Windows")

        self.assertEqual(spec.argv, ("cmd.exe", "/k", "claude --resume"))
        self.assertEqual(spec.cwd, folder)

    def test_empty_command_and_unknown_platform_are_rejected(self):
        with self.assertRaises(LaunchError):
            build_launch_spec(Path("/tmp"), "", system="Darwin")
        with self.assertRaises(LaunchError):
            build_launch_spec(Path("/tmp"), "codex", system="Linux")

    def test_open_folder_uses_native_file_manager(self):
        folder = Path("/tmp/Project")

        self.assertEqual(build_open_folder_spec(folder, system="Darwin").argv, ("open", str(folder)))
        self.assertEqual(
            build_open_folder_spec(folder, system="Windows").argv,
            ("explorer.exe", str(folder)),
        )

    def test_rejects_empty_and_multiline_commands(self):
        self.assertEqual(validate_launch_command(" codex --fast "), "codex --fast")
        for command in ("", "codex\nrm", "codex\0bad"):
            with self.assertRaises(LaunchError):
                validate_launch_command(command)


class WorkspaceLauncherTests(unittest.TestCase):
    def test_iterm_attach_uses_tmux_control_mode(self):
        spec = build_workspace_attach_spec(
            "harness-demo-12345678",
            Path("/opt/homebrew/bin/tmux"),
            use_iterm=True,
        )

        self.assertEqual(spec.argv[:2], ("osascript", "-e"))
        self.assertIn('tell application "iTerm2"', spec.argv[2])
        self.assertIn("create window with default profile command", spec.argv[2])
        self.assertNotIn("write text", spec.argv[2])
        self.assertIn(
            "/opt/homebrew/bin/tmux -CC attach -t harness-demo-12345678",
            spec.argv[2],
        )

    def test_terminal_fallback_uses_standard_tmux_attach(self):
        spec = build_workspace_attach_spec(
            "harness-demo-12345678",
            Path("/opt/homebrew/bin/tmux"),
            use_iterm=False,
        )

        self.assertIn('tell application "Terminal"', spec.argv[2])
        self.assertIn("tmux attach -t harness-demo-12345678", spec.argv[2])
        self.assertNotIn("-CC", spec.argv[2])

    def test_find_iterm_checks_system_and_user_applications(self):
        existing = {Path("/Users/me/Applications/iTerm.app")}

        found = find_iterm_app(
            home=Path("/Users/me"),
            is_dir=lambda path: path in existing,
        )

        self.assertEqual(found, Path("/Users/me/Applications/iTerm.app"))

    @mock.patch("harness.launcher.subprocess.Popen")
    @mock.patch("harness.launcher.find_iterm_app", return_value=Path("/Applications/iTerm.app"))
    def test_launch_workspace_prefers_iterm(self, _find, popen):
        application = launch_workspace(
            "harness-demo-12345678",
            Path("/opt/homebrew/bin/tmux"),
        )

        self.assertEqual(application, "iTerm2")
        self.assertIn("iTerm2", popen.call_args.args[0][2])


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

    def test_creates_titled_panes_and_reapplies_tiled_layout(self):
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
        self.assertEqual(result.tmux_path, Path("tmux"))
        new_session = next(argv for argv, _ in calls if "new-session" in argv)
        self.assertIn(("-x", "200"), tuple(zip(new_session, new_session[1:])))
        self.assertIn(("-y", "60"), tuple(zip(new_session, new_session[1:])))
        self.assertTrue(any("split-window" in argv for argv, _ in calls))
        self.assertTrue(any(argv[-1] == "tiled" for argv, _ in calls))
        self.assertEqual(sum("select-pane" in argv for argv, _ in calls), 2)
        self.assertTrue(any("remain-on-exit" in argv for argv, _ in calls))
        self.assertTrue(any("after-kill-pane" in argv for argv, _ in calls))
        self.assertTrue(any("%1" in argv and "Claude · docs" in argv for argv, _ in calls))

    def test_existing_session_is_reused_without_starting_agents(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(tuple(argv))
            if argv[1] == "list-panes":
                return Completed(stdout="%0\n%1\n")
            return Completed()

        result = start_workspace(self.root, self.entries, run=run, tmux="tmux")

        self.assertTrue(result.reused)
        self.assertEqual(result.pane_count, 2)
        self.assertEqual(len(calls), 2)
        self.assertIn("has-session", calls[0])
        self.assertIn("list-panes", calls[1])

    def test_retiles_after_each_added_pane(self):
        calls = []
        entries = tuple(
            WorkspaceEntry(self.root, f"Agent {index}", "agent", f"Agent {index}")
            for index in range(6)
        )
        next_pane = 1

        def run(argv, **kwargs):
            nonlocal next_pane
            calls.append(tuple(argv))
            if argv[1] == "has-session":
                return Completed(1)
            if argv[1] == "split-window":
                pane = next_pane
                next_pane += 1
                return Completed(stdout=f"%{pane}\n")
            return Completed()

        start_workspace(self.root, entries, run=run, tmux="tmux")

        split_indexes = [index for index, argv in enumerate(calls) if "split-window" in argv]
        layout_indexes = [index for index, argv in enumerate(calls) if "select-layout" in argv]
        self.assertEqual(len(layout_indexes), len(split_indexes))
        for position, split_index in enumerate(split_indexes):
            next_split = split_indexes[position + 1] if position + 1 < len(split_indexes) else len(calls)
            self.assertTrue(any(split_index < layout < next_split for layout in layout_indexes))

    def test_existing_session_reopens_when_assignments_are_now_empty(self):
        def run(argv, **kwargs):
            if argv[1] == "list-panes":
                return Completed(stdout="%0\n")
            return Completed()

        result = start_workspace(self.root, (), run=run, tmux="tmux")

        self.assertTrue(result.reused)
        self.assertEqual(result.pane_count, 1)

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
        self.assertEqual(calls[0][3], workspace_session_name(self.root))

    def test_finds_homebrew_tmux_when_gui_path_is_empty(self):
        homebrew = Path("/opt/homebrew/bin/tmux")

        found = find_tmux(
            which=lambda _name: None,
            is_file=lambda path: path == homebrew,
        )

        self.assertEqual(found, homebrew)


class AppAgentTests(unittest.TestCase):
    def test_root_and_child_assignment_keys(self):
        root = Path("/project")

        self.assertEqual(assignment_key(root, root), ".")
        self.assertEqual(assignment_key(root, root / "src"), "src")

    def test_missing_agent_label_is_explicit(self):
        agent = Agent("known", "My Codex", "codex", None, "#7C3AED")

        self.assertEqual(resolve_agent_label("known", {"known": agent}), "My Codex")
        self.assertEqual(resolve_agent_label("deleted", {"known": agent}), "Missing agent")
        self.assertEqual(tree_agent_label("known", {"known": agent}), "●  My Codex")
        self.assertEqual(tree_agent_label(None, {"known": agent}), "Not assigned")

    def test_launch_requires_resolved_agent_and_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            agent = Agent("known", "My Codex", "codex", None, "#7C3AED")

            self.assertTrue(can_launch("known", {"known": agent}, folder))
            self.assertFalse(can_launch("deleted", {"known": agent}, folder))

        self.assertFalse(can_launch("known", {"known": agent}, folder))


class WorkspaceControlStateTests(unittest.TestCase):
    def test_disabled_without_project_or_valid_assignments(self):
        self.assertEqual(
            workspace_control_state(False, False, False),
            ("Open Workspace", False, False),
        )
        self.assertEqual(
            workspace_control_state(True, False, False),
            ("Open Workspace", False, False),
        )

    def test_open_and_show_states(self):
        self.assertEqual(
            workspace_control_state(True, True, False),
            ("Open Workspace", True, False),
        )
        self.assertEqual(
            workspace_control_state(True, True, True),
            ("Show Workspace", True, True),
        )
        self.assertEqual(
            workspace_control_state(True, False, True),
            ("Show Workspace", True, True),
        )


class FakeTree:
    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 200

    def winfo_width(self):
        return 300

    def winfo_height(self):
        return 100

    def identify_row(self, y):
        return "row-3" if y == 25 else ""


class WidgetHelperTests(unittest.TestCase):
    def test_fallback_initial_uses_first_visible_character(self):
        self.assertEqual(fallback_initial("  Claude"), "C")
        self.assertEqual(fallback_initial(""), "?")

    def test_tree_row_at_pointer_converts_screen_to_widget_coordinates(self):
        self.assertEqual(tree_row_at_pointer(FakeTree(), 130, 225), "row-3")
        self.assertEqual(tree_row_at_pointer(FakeTree(), 130, 260), "")
        self.assertEqual(tree_row_at_pointer(FakeTree(), 450, 225), "")


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


class BuildScriptTests(unittest.TestCase):
    def test_macos_build_creates_windowed_onedir_app(self):
        command = build_command(system="Darwin")

        self.assertIn("--windowed", command)
        self.assertIn("--onedir", command)
        self.assertEqual(command[command.index("--name") + 1], "HarnessDashboard")
        self.assertEqual(
            command[command.index("--add-data") + 1],
            f"{PROJECT_ROOT / 'assets'}:assets",
        )
        self.assertEqual(command[-1], "app.py")

    def test_build_uses_project_local_pyinstaller_cache(self):
        environment = build_environment({"PATH": "/usr/bin"})

        self.assertEqual(environment["PATH"], "/usr/bin")
        self.assertEqual(
            environment["PYINSTALLER_CONFIG_DIR"],
            str(PROJECT_ROOT / "build" / ".pyinstaller-config"),
        )

    def test_windows_build_uses_the_native_add_data_separator(self):
        command = build_command(system="Windows")

        self.assertEqual(
            command[command.index("--add-data") + 1],
            f"{PROJECT_ROOT / 'assets'};assets",
        )


if __name__ == "__main__":
    unittest.main()
