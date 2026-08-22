# Agent Registry and Command Center UI Design

## Goal

Replace the fixed Codex, Claude, and Gemini list with a user-managed Agent Registry and redesign the Tkinter interface as a dark Command Center. A user can add, edit, and delete agents; distinguish them by an image and accent color; and assign them to project folders by click or drag and drop.

## Product Decisions

- The app does not detect installed CLIs, subscriptions, accounts, or login state.
- The user is the source of truth for which agents exist.
- One Agent Registry is shared by every project opened on the same computer.
- Project files store only the stable ID of the assigned agent.
- The application remains Tkinter-based for this iteration.
- The visual design follows the approved three-pane Command Center mockup.

## Agent Registry

Each agent has these fields:

```json
{
  "id": "b85f743a-64c9-41b2-bdb6-b886ff7d25d1",
  "name": "Claude Personal",
  "command": "claude",
  "image": "images/b85f743a-64c9-41b2-bdb6-b886ff7d25d1.png",
  "color": "#D97706"
}
```

- `id` is generated once with UUID4 and never changes.
- `name` is the label shown in the UI and does not need to be unique.
- `command` is the exact command text executed in the terminal. It may include arguments but cannot be empty or contain a newline or NUL character.
- `image` is optional. The MVP accepts PNG images only and copies them into the app data directory so the source file may later move or disappear.
- `color` is selected from a fixed accessible palette and is used for card borders, badges, and the fallback avatar.
- When no image is supplied, the card shows the first visible character of the agent name.

The registry is stored as JSON in the operating-system app data location:

- macOS: `~/Library/Application Support/HarnessDashboard/agents.json`
- Windows: `%APPDATA%\HarnessDashboard\agents.json`

Agent images live in the adjacent `images/` directory. Registry saves use a temporary file followed by `os.replace`, matching the existing project configuration safety behavior.

## Initial Migration

On first launch after this update, if no global registry exists, create removable starter entries for Codex, Claude, and Gemini. This preserves the current application behavior without attempting installation detection.

Existing project assignments use display names. When a project is opened:

1. Match `Codex`, `Claude`, and `Gemini` values to the starter entries by name.
2. Replace matched names with their stable IDs on the next assignment save.
3. Preserve unmatched values as missing assignments rather than silently discarding them.

The project configuration version advances from `1` to `2`:

```json
{
  "version": 2,
  "assignments": {
    "01_research": "b85f743a-64c9-41b2-bdb6-b886ff7d25d1"
  }
}
```

## Deletion Behavior

Deleting an agent removes it from the global registry and deletes its copied image. The app asks for confirmation first.

Projects may exist anywhere on disk, so deletion does not search for and rewrite project files. If an opened project references a deleted agent ID, its folder shows a `Missing agent` badge. The user can assign another agent or remove the assignment. This avoids hidden cross-project mutations.

## Command Center Layout

The main window expands to a minimum of 1100 by 680 pixels and has three visual zones:

1. A narrow navigation rail for Projects and Agent Settings.
2. A center workspace containing the project path, folder tree, assignment badges, and selected-folder action panel.
3. A right Agent Dock containing user-defined agent cards and a Manage button.

The interface uses a dark navy palette, stronger spacing, rounded-card effects simulated with Canvas shapes where useful, and one violet-to-cyan accent. Native controls remain readable under both macOS and Windows Tk themes.

The Agent Dock displays each card with image or fallback avatar, display name, command, and accent color. It never claims that an agent is installed or ready.

## Agent Settings

The Manage button opens a modal `Toplevel` window. The left side lists existing agents. The right side contains the add/edit form:

- image picker and preview;
- display name;
- launch command;
- accent color palette;
- Save button;
- Delete button when editing an existing agent.

Saving validates all fields before modifying the registry. Closing the modal refreshes the Agent Dock and every visible assignment badge. Renaming an agent updates all visible labels because projects refer to stable IDs.

## Assignment Interactions

Two assignment paths are supported:

### Click

1. Select a folder in the project tree.
2. Click an Agent Dock card.
3. The selected folder receives that agent immediately and the project configuration is saved.

### Drag and drop

1. Press an Agent Dock card and move the pointer.
2. A small floating card follows the pointer.
3. The folder row under the pointer receives a violet highlight.
4. Releasing over a valid row assigns the agent and saves the project configuration.
5. Releasing elsewhere cancels without changing data.

Tkinter has no required native dependency for this internal drag operation. Mouse bindings, pointer coordinates, and Treeview row hit testing implement the gesture. External file drag and drop is outside scope.

The selected-folder action panel also offers `Remove assignment` and `Open Terminal`. `Open Terminal` is enabled only when the selected folder exists and its agent ID resolves in the current registry.

## Terminal Launch

The launcher accepts an `Agent` value rather than looking up a fixed command dictionary. The command text comes only from the local user-managed registry.

- On macOS, the folder path remains shell-quoted and the command is embedded in the Terminal AppleScript.
- On Windows, `cmd.exe /k` receives the configured command text while the folder is passed separately as the process working directory.
- Empty commands, newline characters, NUL characters, unknown agent IDs, and missing folders are rejected before launch.

The app does not interpret subscriptions or authenticate the CLI.

## Code Structure

```text
app.py                         # Entry point and Command Center coordination
harness/
├── agent_registry.py          # Agent model, app-data paths, load/save, image copies
├── config.py                  # Project assignment v1 migration and v2 persistence
├── launcher.py                # Launch configured Agent commands
├── scanner.py                 # Existing folder traversal
├── settings_window.py         # Agent add/edit/delete modal
└── widgets.py                 # Agent cards and internal drag gesture
tests/
└── test_harness.py            # Registry, migration, launcher, and interaction helpers
```

The new files correspond to real boundaries: registry persistence, the settings modal, and reusable agent-card drag behavior. No plugin system, theme editor, or UI framework migration is introduced.

## Error Handling

- Invalid registry JSON shows an error and is never overwritten automatically.
- Failed image copies leave the previous agent unchanged.
- Unsupported or corrupt images show the fallback avatar and a warning in Settings.
- A failed project assignment save restores the previous badge and assignment.
- A deleted or missing agent never launches a stale command.
- A drag canceled outside the tree has no side effect.

## Testing

Automated standard-library tests cover:

- registry creation, validation, atomic round-trip, edit, and deletion;
- deterministic starter agents without installation detection;
- PNG copying and old-image cleanup;
- version 1 display-name migration to version 2 stable IDs;
- preservation and display state for missing agent IDs;
- configured commands with arguments on macOS and Windows;
- rejection of unsafe command control characters;
- pure drag/drop target resolution and assignment behavior;
- existing scanner and build behavior.

Visual verification covers the Command Center layout, image fallback, Settings add/edit/delete, click assignment, drag assignment, missing-agent badge, and terminal launch. The macOS `.app` is rebuilt and launched after the automated suite passes.

## Acceptance Criteria

- Agent Dock contents come only from the user-managed registry.
- The user can add, edit, and delete an agent in Settings.
- Each agent can have a PNG image and accent color.
- Renaming an agent does not break existing project assignments.
- Clicking an agent assigns it to the selected folder.
- Dragging an agent onto a folder assigns it and visibly highlights the target.
- Deleting an assigned agent produces a visible missing state instead of launching stale data.
- Existing version 1 projects migrate without losing matched assignments.
- The redesigned UI remains usable at the declared minimum window size.
- The macOS app bundle builds and starts after the redesign.
