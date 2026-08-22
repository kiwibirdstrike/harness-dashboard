import tempfile
import unittest
from pathlib import Path

from harness.config import ConfigError, load_assignments, save_assignments
from harness.scanner import scan_folders


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


if __name__ == "__main__":
    unittest.main()
