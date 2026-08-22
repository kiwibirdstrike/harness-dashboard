import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import assignment_key, can_launch, resolve_agent_label
from harness.agent_registry import Agent, AgentRegistry, RegistryError, app_data_dir
from harness.config import ConfigError, load_assignments, save_assignments
from harness.launcher import LaunchError, build_launch_spec
from harness.scanner import scan_folders
from harness.settings_window import validate_form
from harness.widgets import fallback_initial, tree_row_at_pointer
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
            registry.delete(agents[0].id)
            self.assertEqual([agent.name for agent in registry.load()], ["Claude", "Gemini"])

    def test_invalid_json_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agents.json"
            path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(RegistryError):
                AgentRegistry(Path(tmp)).load()

            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

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


class AppAgentTests(unittest.TestCase):
    def test_root_and_child_assignment_keys(self):
        root = Path("/project")

        self.assertEqual(assignment_key(root, root), ".")
        self.assertEqual(assignment_key(root, root / "src"), "src")

    def test_missing_agent_label_is_explicit(self):
        agent = Agent("known", "My Codex", "codex", None, "#7C3AED")

        self.assertEqual(resolve_agent_label("known", {"known": agent}), "My Codex")
        self.assertEqual(resolve_agent_label("deleted", {"known": agent}), "Missing agent")

    def test_launch_requires_resolved_agent_and_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            agent = Agent("known", "My Codex", "codex", None, "#7C3AED")

            self.assertTrue(can_launch("known", {"known": agent}, folder))
            self.assertFalse(can_launch("deleted", {"known": agent}, folder))

        self.assertFalse(can_launch("known", {"known": agent}, folder))


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
        self.assertEqual(command[-1], "app.py")

    def test_build_uses_project_local_pyinstaller_cache(self):
        environment = build_environment({"PATH": "/usr/bin"})

        self.assertEqual(environment["PATH"], "/usr/bin")
        self.assertEqual(
            environment["PYINSTALLER_CONFIG_DIR"],
            str(PROJECT_ROOT / "build" / ".pyinstaller-config"),
        )


if __name__ == "__main__":
    unittest.main()
