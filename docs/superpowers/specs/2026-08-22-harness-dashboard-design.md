# AI Harness Dashboard MVP Design

## Goal

Build a small desktop application that users can download from GitHub on macOS or Windows. It opens a project folder, presents its directory structure as work areas, assigns a local CLI agent to each folder, persists those assignments, and launches the selected agent in the platform terminal from the correct folder.

## Scope

The MVP supports four user actions:

1. Choose a project folder.
2. Browse its visible directory structure.
3. Assign Codex, Claude, Gemini, or no agent to a folder.
4. Open Terminal in that folder and start the assigned CLI.

The MVP does not coordinate agents, monitor their sessions, edit prompts, synchronize outputs, install CLI tools, or update itself. Distribution consists of source code and downloadable macOS and Windows builds published through GitHub Releases.

## Platform and Technology

- Initial release platforms: macOS 15 or newer on Apple Silicon, and Windows 10 or newer on x64
- Runtime: Python 3.10 or newer
- UI: Tkinter from the Python standard library
- Persistence: JSON file stored at `<project>/.harness.json`
- Terminal integration: AppleScript on macOS and a new `cmd.exe` console on Windows
- Application packaging: PyInstaller
- Distribution: GitHub repository and GitHub Releases

The application itself uses only the Python standard library. PyInstaller is a build-time dependency used to create a macOS application bundle and Windows executable. GitHub Actions builds each platform on its native runner because PyInstaller does not cross-compile.

## User Interface

The main window has three areas:

- Header: selected project path and an “Open Folder” button.
- Folder tree: a hierarchical list of directories under the selected project.
- Details panel: selected folder path, agent selector, save action, and “Open Terminal” action.

The app starts with no project selected. Choosing a project populates the tree and loads any existing `.harness.json`. Selecting a tree item shows its current assignment. Changing the assignment saves it immediately. The launch button is disabled when no agent is assigned.

## Folder Scanning

Only directories are shown. The scanner skips:

- hidden directories whose names start with `.`
- `node_modules`
- `__pycache__`
- `.venv` and `venv`
- `dist` and `build`

Symbolic-link directories are not traversed. Unreadable directories are skipped without aborting the scan. The project root is always represented.

## Agent Model

The built-in agents are fixed for the MVP:

| Display name | Command |
| --- | --- |
| Codex | `codex` |
| Claude | `claude` |
| Gemini | `gemini` |

Assignments are keyed by project-relative POSIX paths. The root folder uses `.`.

Example:

```json
{
  "version": 1,
  "assignments": {
    "01_research": "Gemini",
    "02_planning": "Claude",
    "03_implementation": "Codex"
  }
}
```

Unknown agent names in an existing file are ignored. Invalid JSON produces a visible error and leaves the project unmodified.

## Terminal Launch

Launching validates that the selected folder still exists and that the assigned command is one of the built-in commands.

On macOS, the app asks Terminal to:

1. open a new terminal window;
2. change to the selected folder;
3. run the agent command.

Folder paths are shell-quoted before they are embedded in the command. The app reports launch failures in a dialog. It does not check whether a CLI is installed before launch because the resulting shell error is already clear and preserves the normal terminal environment.

On Windows, the app starts a new `cmd.exe` console with the selected folder as its working directory and runs the agent command. Windows arguments are passed as a list rather than concatenated into a shell string. The console remains open after the CLI exits so the user can read any error output.

Unsupported operating systems show a clear error and do not attempt a launch.

## Code Structure

```text
harness_dashboard/
├── app.py                  # Tkinter entry point and UI state
├── harness/
│   ├── __init__.py
│   ├── scanner.py          # Safe directory traversal
│   ├── config.py           # .harness.json load/save
│   └── launcher.py         # Agent registry and platform terminal launch
├── tests/
│   └── test_harness.py     # Scanner, persistence, and launcher checks
├── scripts/
│   └── build.py            # Repeatable local PyInstaller build
├── .github/
│   └── workflows/
│       └── release.yml     # macOS and Windows release artifacts
├── requirements-build.txt  # Pinned PyInstaller build dependency
└── README.md               # Source and release usage instructions
```

The UI calls three small modules. `scanner.py` has no UI dependency. `config.py` only handles validated JSON data. `launcher.py` selects the platform-specific launch behavior. This separation keeps non-visual behavior runnable through a single standard-library test file.

## Delivery Sequence

The product remains one codebase. Delivery is intentionally phased:

1. Complete and verify the full source application on macOS.
2. Build and smoke-test the macOS `.app` bundle.
3. Add the small Windows terminal-launch branch.
4. Build and smoke-test the Windows `.exe` on a Windows GitHub Actions runner or Windows machine.
5. Publish both archives from the same GitHub repository.

Windows support must not require a second UI, scanner, configuration format, or project structure. Only the launcher implementation and native packaging output differ.

## Distribution

The GitHub repository supports two usage paths:

1. Clone or download the source and run `python app.py` with Python 3.10 or newer.
2. Download a platform build from GitHub Releases and run it without installing Python.

Pushing a version tag matching `v*` starts GitHub Actions builds on `macos-15` and `windows-latest`. The macOS runner produces an Apple Silicon zipped `.app`; the Windows runner produces a zipped x64 application directory containing the `.exe`. The workflow attaches both archives to the matching GitHub Release. An Intel Mac build can be added later from the same source using the `macos-15-intel` runner if actual users need it.

Code signing, notarization, a Windows installer, and automatic updates are outside the MVP. macOS Gatekeeper and Windows SmartScreen may therefore warn users about unsigned downloads; the README must state this limitation and show the platform-native way to approve a trusted download.

## Error Handling

- Folder chooser cancellation leaves the current project unchanged.
- Invalid or unreadable configuration displays an error and does not overwrite the file.
- Failed scans display an error while preserving the current UI state.
- Missing selected folders disable launching and prompt the user to refresh by reopening the project.
- Terminal launch errors and unsupported platforms are displayed with the system error text.

Configuration saves use a temporary sibling file followed by `os.replace` so an interrupted write does not truncate the existing configuration.

## Testing

Use `unittest` from the standard library.

Automated checks cover:

- excluded and hidden directories are not returned;
- symbolic links are not traversed;
- assignments round-trip through `.harness.json`;
- invalid configuration is rejected without rewriting it;
- macOS terminal commands quote folders containing spaces and apostrophes;
- Windows launch arguments preserve folders containing spaces;
- only built-in agent commands can be launched;
- platform selection chooses the correct launcher and rejects unsupported systems.

The first verification milestone runs the full unit-test suite, compiles every Python file, and creates a macOS PyInstaller artifact. The second milestone runs the same tests and creates the Windows artifact on Windows. GitHub Actions ultimately repeats tests and packaging on both platforms. A manual smoke check on each platform opens the app, selects a temporary folder, assigns an agent, confirms that the saved JSON is reflected after reopening the project, and launches one installed CLI. Interactive terminal startup is not part of the automated test suite.

## Acceptance Criteria

- Running `python app.py` opens the dashboard on macOS and Windows.
- A user can select any readable project folder and see its directory hierarchy.
- A user can assign Codex, Claude, or Gemini to any displayed folder.
- Assignments persist in `.harness.json` and reload correctly.
- A user can open the platform terminal at an assigned folder with the corresponding CLI command.
- Invalid configuration, missing folders, and launch failures do not crash the app.
- The source application has no third-party runtime dependencies.
- A GitHub tag build produces downloadable macOS and Windows archives.
- Downloaded release builds run without a separate Python installation.
