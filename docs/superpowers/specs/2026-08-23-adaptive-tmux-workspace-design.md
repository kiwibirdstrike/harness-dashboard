# Adaptive tmux Workspace Design

## Goal

Let a user launch several assigned Agent CLIs and see them together in one external terminal window. Harness chooses a readable pane layout from the number of active sessions instead of assuming four terminals.

The first implementation targets macOS and uses iTerm2 as the visible terminal application with `tmux` for pane management, resizing, and session persistence. Harness remains the controller; it does not implement a terminal emulator.

## User Experience

The selected project gains a workspace launch action. Launching a workspace opens one iTerm2 window attached to a Harness-owned `tmux` session. Every assigned folder becomes one independent pane whose title identifies the Agent and folder.

The layout adapts whenever Harness adds or removes a pane. Harness asks tmux to apply its built-in `tiled` layout rather than simulating repeated iTerm2 `Command-D` splits:

| Active panes | Layout |
| --- | --- |
| 1 | One full pane |
| 2 | Two equal columns |
| 3 | Balanced tiled arrangement using both axes |
| 4 | 2 × 2 |
| 5+ | Near-square tiled grid selected by tmux |

The `tiled` preset keeps the number of rows and columns close and gives panes comparable space. This avoids the narrow-pane problem caused by repeatedly splitting only left-to-right or top-to-bottom. A pane can still use tmux's standard zoom toggle, so the user can temporarily focus on one Agent and return to the grid.

Closing the external Terminal window does not automatically kill the Agents. Relaunching the same Harness workspace reattaches to the existing session. An explicit **Stop Workspace** action terminates all panes after confirmation.

## Interface Changes

The existing **Open Terminal** action remains the single-folder shortcut and keeps its current behavior.

A new **Open Workspace** action launches all currently assigned folders under the selected project root. When a managed session exists, the label becomes **Show Workspace**. A secondary **Stop Workspace** action appears only while that session exists.

The Harness status line reports concise states such as `4 terminals running`, `Workspace reopened`, or `tmux is required`.

## Architecture

### Workspace description

The UI converts current assignments into immutable launch entries containing:

- assignment key
- absolute folder path
- Agent name
- Agent command
- pane title

Invalid assignments, deleted Agents, and missing folders are skipped and reported before any session is created. An empty valid entry list does not launch a workspace.

### tmux controller

A focused controller module owns all tmux commands:

- detect whether `tmux` is available
- create a named detached session
- add panes with explicit working directories and commands
- assign pane titles
- apply the adaptive layout
- detect and reattach an existing session
- stop only the session owned by the current project

Session names use a stable, sanitized project identifier plus a short hash of the absolute project path. This prevents projects with the same folder name from sharing a session.

Commands are passed as argument arrays. Folder paths and configured Agent commands are not interpolated into one large shell script. Existing one-line command validation remains the trust-boundary check.

### iTerm2 launcher

After the detached session is ready, the macOS launcher opens iTerm2 and runs only `tmux -CC attach` for the Harness-owned session. iTerm2's tmux control mode renders tmux panes as native iTerm2 panes while tmux retains session persistence.

If iTerm2 is unavailable, Harness automatically falls back to the built-in Terminal app with a standard `tmux attach`, preserving the same pane layout with a less integrated appearance. Harness reports which application was opened.

### Layout policy

After creating or removing a pane, the controller applies `select-layout tiled`. The layout policy is therefore a small, deterministic tmux command rather than custom geometry code.

## Failure Handling

- Missing `tmux`: show an explanation and the installation command; do not modify project configuration.
- Missing iTerm2: use the built-in Terminal fallback and report it; do not install iTerm2 automatically.
- Partial session creation: kill the newly created Harness session so no orphaned panes remain.
- Existing session: reattach instead of creating duplicate Agents.
- Invalid assignment: skip it, list the affected folder, and continue only if at least one valid pane remains.
- Pane process exits: leave the pane visible so its error can be read; the user may close it or relaunch the workspace.
- Stop action: target only the generated session name for the current project.

## Compatibility

This phase is macOS-only. The controller boundary is platform-neutral enough for a later Windows implementation, but Windows must use Windows Terminal or WSL and is not part of this change.

No automatic package installation is performed. Harness detects iTerm2 and `tmux` because changing a user's system is outside the app's responsibility.

## Testing

- Unit-test that pane creation and removal always reapplies the `tiled` layout.
- Unit-test stable and collision-resistant session naming.
- Unit-test launch-entry filtering for deleted Agents and missing folders.
- Unit-test generated tmux argument arrays and cleanup after partial failure.
- Keep existing single-folder Terminal launch tests unchanged.
- Run a macOS smoke test with 1, 2, 3, 4, 6, and 10 short-lived shell panes.
- Build the packaged app and verify that it detects the host iTerm2 and `tmux`, opens one iTerm2 window through tmux control mode, reattaches, and stops only its own session.
- Verify the built-in Terminal fallback separately when iTerm2 detection is disabled.

## Out of Scope

- Embedded terminal rendering inside the Tkinter window
- Installing or updating `tmux`
- Windows workspace launch
- Persisting terminal output after the tmux session is explicitly stopped
- Remote Agents, SSH orchestration, shared input, and session recording
