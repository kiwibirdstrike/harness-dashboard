# Adaptive tmux Workspace Design

## Goal

Let a user launch several assigned Agent CLIs and see them together in one external terminal window. Harness chooses a readable pane layout from the number of active sessions instead of assuming four terminals.

The first implementation targets macOS and uses `tmux` for terminal emulation, pane management, resizing, and session persistence. Harness remains the controller; it does not implement a terminal emulator.

## User Experience

The selected folders gain a workspace launch action. Launching a workspace opens one Terminal window attached to a Harness-owned `tmux` session. Every assigned folder becomes one independent pane whose title identifies the Agent and folder.

The layout adapts whenever Harness adds or removes a pane:

| Active panes | Layout |
| --- | --- |
| 1 | One full pane |
| 2 | Two equal columns |
| 3 | Two panes above, one wide pane below |
| 4 | 2 × 2 |
| 5–6 | 3 × 2 |
| 7–9 | 3 × 3 |
| 10+ | Near-square grid, such as 4 × 3 for 10–12 and 4 × 4 for 13–16 |

For counts not represented by a native `tmux` preset, Harness chooses columns and rows near the square root of the pane count and calculates pane percentages while constructing the split tree. This is the practical external-window equivalent of responsive wrapping because tmux does not provide a scrolling pane canvas. A pane can still use tmux's standard zoom toggle, so the user can temporarily focus on one Agent and return to the grid.

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

### Native Terminal launcher

After the detached session is ready, the existing macOS launcher opens Terminal and runs only the tmux attach command. This reuses the current AppleScript boundary instead of adding another automation layer.

### Layout policy

Layout selection is a pure function of pane count. Named tmux layouts are used when they produce the intended result; otherwise the controller applies deterministic horizontal and vertical splits. Keeping this policy independent from process execution makes it testable without launching Terminal.

## Failure Handling

- Missing `tmux`: show an explanation and the installation command; do not modify project configuration.
- Partial session creation: kill the newly created Harness session so no orphaned panes remain.
- Existing session: reattach instead of creating duplicate Agents.
- Invalid assignment: skip it, list the affected folder, and continue only if at least one valid pane remains.
- Pane process exits: leave the pane visible so its error can be read; the user may close it or relaunch the workspace.
- Stop action: target only the generated session name for the current project.

## Compatibility

This phase is macOS-only. The controller boundary is platform-neutral enough for a later Windows implementation, but Windows must use Windows Terminal or WSL and is not part of this change.

No automatic package installation is performed. Harness detects `tmux` and explains the requirement because changing a user's system is outside the app's responsibility.

## Testing

- Unit-test pane-count-to-layout decisions for 1 through 10 panes.
- Unit-test stable and collision-resistant session naming.
- Unit-test launch-entry filtering for deleted Agents and missing folders.
- Unit-test generated tmux argument arrays and cleanup after partial failure.
- Keep existing single-folder Terminal launch tests unchanged.
- Run a macOS smoke test with 1, 2, 3, 4, 6, and 10 short-lived shell panes.
- Build the packaged app and verify that it detects the host `tmux`, opens one Terminal window, reattaches, and stops only its own session.

## Out of Scope

- Embedded terminal rendering inside the Tkinter window
- Installing or updating `tmux`
- Windows workspace launch
- Persisting terminal output after the tmux session is explicitly stopped
- Remote Agents, SSH orchestration, shared input, and session recording
