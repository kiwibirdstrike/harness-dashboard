import tempfile
import unittest
from pathlib import Path

from app import assignment_key, can_launch
from harness.config import ConfigError, load_assignments, save_assignments
from harness.launcher import LaunchError, build_launch_spec
from harness.scanner import scan_folders
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
            expected = {"research": "Gemini", "src": "Codex"}

            save_assignments(root, expected)

            self.assertEqual(load_assignments(root), expected)

    def test_unknown_agents_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness.json").write_text(
                '{"version": 1, "assignments": {"src": "Other", "docs": "Claude"}}',
                encoding="utf-8",
            )

            self.assertEqual(load_assignments(root), {"docs": "Claude"})

    def test_invalid_json_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".harness.json"
            config.write_text("{broken", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_assignments(root)

            self.assertEqual(config.read_text(encoding="utf-8"), "{broken")


class LauncherTests(unittest.TestCase):
    def test_macos_spec_quotes_shell_path_and_escapes_applescript(self):
        folder = Path('/tmp/Client\'s "Project"')

        spec = build_launch_spec(folder, "Codex", system="Darwin")

        self.assertEqual(spec.argv[:2], ("osascript", "-e"))
        self.assertIn("codex", spec.argv[2])
        self.assertIn("cd ", spec.argv[2])
        self.assertIn('\\"Project\\"', spec.argv[2])

    def test_windows_spec_uses_working_directory_without_path_concatenation(self):
        folder = Path(r"C:\Users\A Person\Project")

        spec = build_launch_spec(folder, "Claude", system="Windows")

        self.assertEqual(spec.argv, ("cmd.exe", "/k", "claude"))
        self.assertEqual(spec.cwd, folder)

    def test_unknown_agent_and_platform_are_rejected(self):
        with self.assertRaises(LaunchError):
            build_launch_spec(Path("/tmp"), "Other", system="Darwin")
        with self.assertRaises(LaunchError):
            build_launch_spec(Path("/tmp"), "Codex", system="Linux")


class AppPathTests(unittest.TestCase):
    def test_root_and_child_assignment_keys(self):
        root = Path("/project")

        self.assertEqual(assignment_key(root, root), ".")
        self.assertEqual(assignment_key(root, root / "src"), "src")

    def test_launch_requires_known_agent_and_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)

            self.assertTrue(can_launch("Codex", folder))
            self.assertFalse(can_launch("Unassigned", folder))

        self.assertFalse(can_launch("Codex", folder))


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
