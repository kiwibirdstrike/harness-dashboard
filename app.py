from __future__ import annotations

import tkinter as tk
from collections.abc import Mapping
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from harness.agent_registry import Agent, AgentRegistry, RegistryError
from harness.config import ConfigError, load_assignments, save_assignments
from harness.launcher import (
    LaunchError,
    launch_agent,
    launch_workspace,
    open_folder as reveal_folder,
)
from harness.scanner import FolderNode, scan_folders
from harness.settings_window import AgentSettingsWindow
from harness.widgets import AgentCard, AgentDragController
from harness.workspace import (
    WorkspaceError,
    WorkspaceSelection,
    collect_workspace_entries,
    start_workspace,
    stop_workspace,
    tmux_available,
    workspace_exists,
)


BG = "#F4F7FB"
PANEL = "#FFFFFF"
PANEL_ALT = "#F8FAFD"
BORDER = "#DDE5F0"
TEXT = "#172033"
MUTED = "#718096"
ACCENT = "#6957E8"
DANGER = "#D84B5B"


def assignment_key(root: Path, folder: Path) -> str:
    relative = folder.relative_to(root)
    return "." if relative == Path(".") else relative.as_posix()


def resolve_agent_label(agent_id: str, agents: Mapping[str, Agent]) -> str:
    agent = agents.get(agent_id)
    return agent.name if agent else "Missing agent"


def tree_agent_label(agent_id: str | None, agents: Mapping[str, Agent]) -> str:
    if not agent_id:
        return "Not assigned"
    return f"●  {resolve_agent_label(agent_id, agents)}"


def can_launch(agent_id: str | None, agents: Mapping[str, Agent], folder: Path) -> bool:
    return bool(agent_id and agent_id in agents and folder.is_dir())


def workspace_control_state(
    has_project: bool,
    has_entries: bool,
    session_exists: bool,
) -> tuple[str, bool, bool]:
    return (
        "Show Workspace" if session_exists else "Open Workspace",
        has_project and (has_entries or session_exists),
        session_exists,
    )


class HarnessDashboard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.registry = AgentRegistry()
        self.agents: dict[str, Agent] = {}
        self.project_root: Path | None = None
        self.selected_folder: Path | None = None
        self.assignments: dict[str, str] = {}
        self.item_paths: dict[str, Path] = {}
        self.project_text = tk.StringVar(value="No project selected")
        self.project_name = tk.StringVar(value="Open a project to begin")
        self.folder_text = tk.StringVar(value="Select a folder from the workspace tree")
        self.assigned_text = tk.StringVar(value="No agent assigned")
        self.status_text = tk.StringVar(value="Ready")
        self.agent_count_text = tk.StringVar(value="0 agents")
        self._configure_styles()
        self._build_window()
        self._reload_agents(show_error=True)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
            borderwidth=0, rowheight=38, font=("TkDefaultFont", 10)
        )
        style.configure(
            "Treeview.Heading", background="#EEF3F9", foreground="#52627A", borderwidth=0,
            relief="flat", padding=(10, 9), font=("TkDefaultFont", 9, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", "#EBE8FF")],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "Action.TButton", background=ACCENT, foreground="#FFFFFF", borderwidth=0,
            padding=(18, 10), font=("TkDefaultFont", 10, "bold")
        )
        style.map("Action.TButton", background=[("active", "#8073FF"), ("disabled", "#29344C")])
        style.configure(
            "Ghost.TButton", background=PANEL, foreground="#46546A",
            bordercolor=BORDER, padding=(14, 9)
        )
        style.map("Ghost.TButton", background=[("active", "#EDF1F7")])
        style.configure(
            "Slim.Vertical.TScrollbar", background="#C8D2E1", troughcolor=BG,
            borderwidth=0, arrowsize=0, width=8
        )

    def _build_window(self) -> None:
        self.root.title("Harness Dashboard")
        self.root.geometry("1220x760")
        self.root.minsize(1100, 680)
        self.root.configure(background=BG)
        self.root.option_add("*tearOff", False)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self._build_workspace()
        self._build_dock()

    def _build_workspace(self) -> None:
        workspace = tk.Frame(self.root, background=BG, padx=26, pady=22)
        workspace.grid(row=0, column=0, sticky="nsew")
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(2, weight=1)
        tk.Label(
            workspace, text="HARNESS DASHBOARD", background=BG, foreground="#7A8AA2",
            font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=0, sticky="w")
        header = tk.Frame(workspace, background=BG)
        header.grid(row=1, column=0, sticky="ew", pady=(5, 18))
        header.columnconfigure(0, weight=1)
        tk.Label(
            header, textvariable=self.project_name, background=BG, foreground=TEXT,
            font=("TkDefaultFont", 23, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="⌂  Set Root", style="Ghost.TButton", command=self.choose_root).grid(
            row=0, column=1, padx=(16, 0)
        )
        self.workspace_button = ttk.Button(
            header,
            text="Open Workspace",
            style="Action.TButton",
            command=self._open_workspace,
            state="disabled",
        )
        self.workspace_button.grid(row=0, column=2, padx=(8, 0))
        self.stop_workspace_button = ttk.Button(
            header,
            text="Stop Workspace",
            style="Ghost.TButton",
            command=self._stop_workspace,
        )
        self.stop_workspace_button.grid(row=0, column=3, padx=(8, 0))
        self.stop_workspace_button.grid_remove()
        tk.Label(
            header, textvariable=self.project_text, background=BG, foreground=MUTED, anchor="w"
        ).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(5, 0))

        tree_panel = tk.Frame(
            workspace, background=PANEL, highlightbackground=BORDER, highlightthickness=1
        )
        tree_panel.grid(row=2, column=0, sticky="nsew")
        tree_panel.columnconfigure(0, weight=1)
        tree_panel.rowconfigure(1, weight=1)
        tk.Label(
            tree_panel, text="PROJECT WORKSPACES", background=PANEL, foreground="#52627A",
            font=("TkDefaultFont", 10, "bold"), padx=18, pady=14
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.tree = ttk.Treeview(
            tree_panel, columns=("agent",), show="tree headings", selectmode="browse"
        )
        self.tree.heading("#0", text="FOLDER", anchor=tk.W)
        self.tree.heading("agent", text="ASSIGNED AGENT", anchor=tk.W)
        self.tree.column("#0", width=430, minwidth=260, stretch=True)
        self.tree.column("agent", width=210, minwidth=210, stretch=False, anchor=tk.W)
        scrollbar = ttk.Scrollbar(
            tree_panel,
            orient=tk.VERTICAL,
            style="Slim.Vertical.TScrollbar",
            command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=(0, 12))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        divider = tk.Frame(tree_panel, background=BORDER, width=1)
        self.tree.bind(
            "<Configure>",
            lambda _event: divider.place(
                x=self.tree.winfo_x() + self.tree.winfo_width() - 211,
                y=self.tree.winfo_y(),
                width=1,
                height=self.tree.winfo_height(),
            ),
            add="+",
        )
        self.tree.tag_configure("missing-agent", foreground=DANGER)

        action = tk.Frame(
            workspace, background=PANEL_ALT, highlightbackground=BORDER,
            highlightthickness=1, padx=18, pady=15
        )
        action.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        action.columnconfigure(0, weight=1)
        tk.Label(
            action, textvariable=self.folder_text, background=PANEL_ALT, foreground=TEXT,
            font=("TkDefaultFont", 11, "bold"), anchor="w"
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            action, textvariable=self.assigned_text, background=PANEL_ALT,
            foreground=MUTED, anchor="w", justify=tk.LEFT, wraplength=390
        ).grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.unassign_button = ttk.Button(
            action, text="Remove Agent", style="Ghost.TButton",
            command=self._unassign_selected, state="disabled"
        )
        self.unassign_button.grid(row=0, column=1, rowspan=2, padx=(12, 8))
        self.folder_button = ttk.Button(
            action,
            text="Open Folder",
            style="Ghost.TButton",
            command=self._open_selected_folder,
            state="disabled",
        )
        self.folder_button.grid(row=0, column=2, rowspan=2, padx=(0, 8))
        self.launch_button = ttk.Button(
            action, text="Open Terminal", style="Action.TButton",
            command=self._open_terminal, state="disabled"
        )
        self.launch_button.grid(row=0, column=3, rowspan=2)
        tk.Label(
            workspace, textvariable=self.status_text, background=BG,
            foreground="#71839F", anchor="w"
        ).grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.drag_controller = AgentDragController(self.root, self.tree, self._drop_agent)

    def _build_dock(self) -> None:
        dock = tk.Frame(
            self.root, width=292, background="#F9FBFE",
            highlightbackground=BORDER, highlightthickness=1
        )
        dock.grid(row=0, column=1, sticky="ns")
        dock.grid_propagate(False)
        dock.columnconfigure(0, weight=1)
        dock.rowconfigure(2, weight=1)
        head = tk.Frame(dock, background="#F9FBFE", padx=18, pady=20)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        tk.Label(
            head, text="AGENT DOCK", background="#F9FBFE", foreground=TEXT,
            font=("TkDefaultFont", 13, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(head, text="Manage", style="Ghost.TButton", command=self.open_settings).grid(
            row=0, column=1
        )
        tk.Label(
            dock, textvariable=self.agent_count_text, background="#F9FBFE",
            foreground=MUTED, anchor="w", padx=18
        ).grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.dock_canvas = tk.Canvas(
            dock, background="#F9FBFE", borderwidth=0, highlightthickness=0
        )
        dock_scroll = ttk.Scrollbar(
            dock,
            orient=tk.VERTICAL,
            style="Slim.Vertical.TScrollbar",
            command=self.dock_canvas.yview,
        )
        self.dock_canvas.configure(yscrollcommand=dock_scroll.set)
        self.dock_canvas.grid(row=2, column=0, sticky="nsew", padx=(14, 0), pady=(0, 16))
        dock_scroll.grid(row=2, column=1, sticky="ns", padx=(0, 6), pady=(0, 16))
        self.cards_frame = tk.Frame(self.dock_canvas, background="#F9FBFE")
        self.cards_window = self.dock_canvas.create_window(
            (0, 0), window=self.cards_frame, anchor="nw"
        )
        self.cards_frame.bind(
            "<Configure>",
            lambda _event: self.dock_canvas.configure(scrollregion=self.dock_canvas.bbox("all")),
        )
        self.dock_canvas.bind(
            "<Configure>",
            lambda event: self.dock_canvas.itemconfigure(self.cards_window, width=event.width),
        )
        self.dock_canvas.bind("<MouseWheel>", self._scroll_dock)
        self.cards_frame.bind("<MouseWheel>", self._scroll_dock)
        tk.Label(
            dock, text="Click to assign • Drag onto a folder", background="#F9FBFE",
            foreground="#8190A6", padx=18, pady=12
        ).grid(row=3, column=0, columnspan=2, sticky="ew")

    def _reload_agents(self, *, show_error: bool = False) -> None:
        try:
            agents = self.registry.load()
        except RegistryError as error:
            self.agents = {}
            if show_error:
                messagebox.showerror("Cannot load agents", str(error), parent=self.root)
        else:
            self.agents = {agent.id: agent for agent in agents}
        self._refresh_dock()
        self._refresh_tree_labels()
        self._refresh_selected()
        self._refresh_workspace_controls()

    def _refresh_dock(self) -> None:
        for child in self.cards_frame.winfo_children():
            child.destroy()
        count = len(self.agents)
        self.agent_count_text.set(f"{count} agent{'s' if count != 1 else ''}")
        if not self.agents:
            tk.Label(
                self.cards_frame, text="No agents yet.\nOpen Manage to add one.",
                background="#F9FBFE", foreground=MUTED, justify=tk.LEFT
            ).pack(fill="x", padx=6, pady=12)
            return
        for agent in self.agents.values():
            card = AgentCard(self.cards_frame, agent, self.registry.root)
            card.pack(fill="x", padx=4, pady=(0, 10))
            card.bind("<MouseWheel>", self._scroll_dock, add="+")
            self.drag_controller.attach(card, self._assign_selected)

    def open_settings(self) -> None:
        AgentSettingsWindow(self.root, self.registry, self._reload_agents)

    def choose_root(self) -> None:
        chosen = filedialog.askdirectory(title="Choose a project folder")
        if not chosen:
            return
        project = Path(chosen).resolve()
        try:
            tree = scan_folders(project)
            assignments = load_assignments(project, list(self.agents.values()))
        except (ConfigError, OSError, ValueError) as error:
            messagebox.showerror("Cannot open project", str(error), parent=self.root)
            return
        self.project_root = project
        self.assignments = assignments
        self.selected_folder = None
        self.project_text.set(str(project))
        self.project_name.set(project.name)
        self._populate_tree(tree)
        self.status_text.set(f"Loaded {project.name}")
        self._refresh_workspace_controls()

    def _populate_tree(self, root_node: FolderNode) -> None:
        self.tree.delete(*self.tree.get_children())
        self.item_paths.clear()
        root_item = self._insert_node("", root_node, open_node=True)
        self.tree.selection_set(root_item)
        self.tree.focus(root_item)
        self.tree.see(root_item)

    def _insert_node(self, parent: str, node: FolderNode, *, open_node: bool = False) -> str:
        if self.project_root is None:
            raise RuntimeError("Project root is not loaded")
        key = assignment_key(self.project_root, node.path)
        agent_id = self.assignments.get(key)
        tags = ("missing-agent",) if agent_id and agent_id not in self.agents else ()
        item = self.tree.insert(
            parent, tk.END, text=f"  ▸  {node.path.name or str(node.path)}",
            values=(tree_agent_label(agent_id, self.agents),),
            tags=tags, open=open_node
        )
        self.item_paths[item] = node.path
        for child in node.children:
            self._insert_node(item, child)
        return item

    def _on_tree_select(self, _event: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.selected_folder = self.item_paths.get(selection[0])
        self._refresh_selected()
        if self.selected_folder and not self.selected_folder.is_dir():
            self.status_text.set("Folder missing. Reopen the project to refresh.")

    def _refresh_selected(self) -> None:
        if self.project_root is None or self.selected_folder is None:
            self.folder_text.set("Select a folder from the workspace tree")
            self.assigned_text.set("No agent assigned")
            self.launch_button.configure(state="disabled")
            self.folder_button.configure(state="disabled")
            self.unassign_button.configure(state="disabled")
            return
        key = assignment_key(self.project_root, self.selected_folder)
        agent_id = self.assignments.get(key)
        self.folder_text.set(self.selected_folder.name or str(self.selected_folder))
        self.assigned_text.set(
            self._selected_agent_summary(agent_id)
            if agent_id else "No agent assigned — choose one from the dock"
        )
        self.folder_button.configure(
            state="normal" if self.selected_folder.is_dir() else "disabled"
        )
        self.launch_button.configure(
            state="normal" if can_launch(agent_id, self.agents, self.selected_folder) else "disabled"
        )
        self.unassign_button.configure(state="normal" if agent_id else "disabled")

    def _assign_selected(self, agent_id: str) -> None:
        selection = self.tree.selection()
        if not selection:
            self.status_text.set("Select a project folder first")
            return
        self._assign_agent(agent_id, selection[0])

    def _drop_agent(self, agent_id: str, item: str) -> None:
        self._assign_agent(agent_id, item)

    def _assign_agent(self, agent_id: str, item: str) -> None:
        if self.project_root is None or agent_id not in self.agents or item not in self.item_paths:
            return
        folder = self.item_paths[item]
        key = assignment_key(self.project_root, folder)
        previous = dict(self.assignments)
        self.assignments[key] = agent_id
        if not self._save_or_restore(previous):
            return
        self._set_item_agent(item, agent_id)
        self.tree.selection_set(item)
        self.selected_folder = folder
        self._refresh_selected()
        self.status_text.set(f"{self.agents[agent_id].name} assigned to {folder.name}")
        self._refresh_workspace_controls()

    def _unassign_selected(self) -> None:
        if self.project_root is None or self.selected_folder is None:
            return
        selection = self.tree.selection()
        if not selection:
            return
        key = assignment_key(self.project_root, self.selected_folder)
        previous = dict(self.assignments)
        self.assignments.pop(key, None)
        if not self._save_or_restore(previous):
            return
        self._set_item_agent(selection[0], None)
        self._refresh_selected()
        self.status_text.set(f"Removed agent from {self.selected_folder.name}")
        self._refresh_workspace_controls()

    def _save_or_restore(self, previous: dict[str, str]) -> bool:
        if self.project_root is None:
            return False
        try:
            save_assignments(self.project_root, self.assignments)
            return True
        except ConfigError as error:
            self.assignments = previous
            messagebox.showerror("Cannot save assignment", str(error), parent=self.root)
            return False

    def _set_item_agent(self, item: str, agent_id: str | None) -> None:
        self.tree.set(item, "agent", tree_agent_label(agent_id, self.agents))
        tags = ("missing-agent",) if agent_id and agent_id not in self.agents else ()
        self.tree.item(item, tags=tags)

    def _refresh_tree_labels(self) -> None:
        if self.project_root is None:
            return
        for item, folder in self.item_paths.items():
            agent_id = self.assignments.get(assignment_key(self.project_root, folder))
            self._set_item_agent(item, agent_id)

    def _open_terminal(self) -> None:
        if self.project_root is None or self.selected_folder is None:
            return
        agent_id = self.assignments.get(assignment_key(self.project_root, self.selected_folder))
        agent = self.agents.get(agent_id or "")
        if agent is None:
            return
        try:
            launch_agent(self.selected_folder, agent.command)
        except LaunchError as error:
            messagebox.showerror("Cannot open terminal", str(error), parent=self.root)
            return
        self.status_text.set(f"Opened {agent.name} in {self.selected_folder.name}")

    def _open_selected_folder(self) -> None:
        if self.selected_folder is None:
            return
        try:
            reveal_folder(self.selected_folder)
        except LaunchError as error:
            messagebox.showerror("Cannot open folder", str(error), parent=self.root)
            return
        self.status_text.set(f"Opened folder: {self.selected_folder.name}")

    def _workspace_selection(self) -> WorkspaceSelection | None:
        if self.project_root is None:
            return None
        return collect_workspace_entries(self.project_root, self.assignments, self.agents)

    def _refresh_workspace_controls(self) -> None:
        selection = self._workspace_selection()
        has_entries = bool(selection and selection.entries)
        exists = False
        if self.project_root is not None and tmux_available():
            try:
                exists = workspace_exists(self.project_root)
            except WorkspaceError:
                exists = False
        label, enabled, show_stop = workspace_control_state(
            self.project_root is not None,
            has_entries,
            exists,
        )
        self.workspace_button.configure(
            text=label,
            state="normal" if enabled else "disabled",
        )
        if show_stop:
            self.stop_workspace_button.grid()
        else:
            self.stop_workspace_button.grid_remove()

    def _open_workspace(self) -> None:
        selection = self._workspace_selection()
        if self.project_root is None or selection is None:
            return
        if not tmux_available():
            messagebox.showerror(
                "tmux is required",
                "Install tmux with 'brew install tmux', then reopen the workspace. "
                "Harness will not install it automatically.",
                parent=self.root,
            )
            return
        try:
            result = start_workspace(self.project_root, selection.entries)
            application = launch_workspace(result.session_name, result.tmux_path)
        except (WorkspaceError, LaunchError) as error:
            messagebox.showerror("Cannot open workspace", str(error), parent=self.root)
            return
        verb = "Reopened" if result.reused else "Opened"
        skipped = f"; skipped {len(selection.skipped)}" if selection.skipped else ""
        self.status_text.set(
            f"{verb} {result.pane_count} terminals in {application}{skipped}"
        )
        if selection.skipped:
            messagebox.showwarning(
                "Some folders were skipped",
                "\n".join(selection.skipped),
                parent=self.root,
            )
        self._refresh_workspace_controls()

    def _stop_workspace(self) -> None:
        if self.project_root is None:
            return
        if not messagebox.askyesno(
            "Stop workspace",
            "Stop every Agent terminal in this project workspace?",
            parent=self.root,
        ):
            return
        try:
            stop_workspace(self.project_root)
        except WorkspaceError as error:
            messagebox.showerror("Cannot stop workspace", str(error), parent=self.root)
            return
        self.status_text.set("Stopped terminal workspace")
        self._refresh_workspace_controls()

    def _selected_agent_summary(self, agent_id: str) -> str:
        agent = self.agents.get(agent_id)
        if agent is None:
            return "Assigned to Missing agent"
        description = f" — {agent.description}" if agent.description else ""
        return f"Assigned to {agent.name}{description}"

    def _scroll_dock(self, event: tk.Event) -> None:
        self.dock_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


def main() -> None:
    root = tk.Tk()
    HarnessDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
