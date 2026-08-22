from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from harness import AGENT_COMMANDS
from harness.config import ConfigError, load_assignments, save_assignments
from harness.launcher import LaunchError, launch_agent
from harness.scanner import FolderNode, scan_folders


UNASSIGNED = "Unassigned"


def assignment_key(root: Path, folder: Path) -> str:
    relative = folder.relative_to(root)
    return "." if relative == Path(".") else relative.as_posix()


def can_launch(command: str | None, folder: Path) -> bool:
    return bool(command and command.strip()) and folder.is_dir()


class HarnessDashboard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.project_root: Path | None = None
        self.selected_folder: Path | None = None
        self.assignments: dict[str, str] = {}
        self.item_paths: dict[str, Path] = {}

        self.project_text = tk.StringVar(value="No project selected")
        self.folder_text = tk.StringVar(value="Select a project folder to begin")
        self.agent_text = tk.StringVar(value=UNASSIGNED)
        self.status_text = tk.StringVar(value="Ready")

        self._build_window()

    def _build_window(self) -> None:
        self.root.title("Harness Dashboard")
        self.root.geometry("980x640")
        self.root.minsize(760, 480)
        self.root.option_add("*tearOff", False)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=(18, 16, 18, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Button(header, text="Open Folder", command=self.open_folder).grid(
            row=0, column=0, padx=(0, 14)
        )
        ttk.Label(header, textvariable=self.project_text).grid(
            row=0, column=1, sticky="w"
        )

        content = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))

        tree_frame = ttk.Frame(content, padding=1)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("agent",),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="Project folders")
        self.tree.heading("agent", text="Agent")
        self.tree.column("#0", width=360, minwidth=220)
        self.tree.column("agent", width=110, minwidth=90, anchor=tk.CENTER)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        content.add(tree_frame, weight=3)

        details = ttk.Frame(content, padding=(24, 18))
        details.columnconfigure(0, weight=1)
        ttk.Label(details, text="Selected workspace", font=("TkDefaultFont", 15, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        ttk.Label(
            details,
            textvariable=self.folder_text,
            wraplength=330,
            justify=tk.LEFT,
        ).grid(row=1, column=0, sticky="ew", pady=(0, 24))
        ttk.Label(details, text="Assigned agent").grid(row=2, column=0, sticky="w")
        self.agent_box = ttk.Combobox(
            details,
            textvariable=self.agent_text,
            values=(UNASSIGNED, *AGENT_COMMANDS),
            state="disabled",
        )
        self.agent_box.grid(row=3, column=0, sticky="ew", pady=(6, 20))
        self.agent_box.bind("<<ComboboxSelected>>", self._on_agent_changed)
        self.launch_button = ttk.Button(
            details,
            text="Open Terminal",
            command=self._open_terminal,
            state="disabled",
        )
        self.launch_button.grid(row=4, column=0, sticky="ew")
        content.add(details, weight=2)

        ttk.Separator(self.root).grid(row=2, column=0, sticky="ew")
        ttk.Label(
            self.root,
            textvariable=self.status_text,
            padding=(18, 8),
        ).grid(row=3, column=0, sticky="ew")

    def open_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Choose a project folder")
        if not chosen:
            return

        project = Path(chosen).resolve()
        try:
            tree = scan_folders(project)
            assignments = load_assignments(project)
        except (ConfigError, OSError, ValueError) as error:
            messagebox.showerror("Cannot open project", str(error))
            return

        self.project_root = project
        self.assignments = assignments
        self.selected_folder = None
        self.project_text.set(str(project))
        self._populate_tree(tree)
        self.status_text.set(f"Loaded {project.name}")

    def _populate_tree(self, root_node: FolderNode) -> None:
        self.tree.delete(*self.tree.get_children())
        self.item_paths.clear()
        root_item = self._insert_node("", root_node, open_node=True)
        self.tree.selection_set(root_item)
        self.tree.focus(root_item)

    def _insert_node(
        self, parent: str, node: FolderNode, *, open_node: bool = False
    ) -> str:
        if self.project_root is None:
            raise RuntimeError("Project root is not loaded")
        key = assignment_key(self.project_root, node.path)
        item = self.tree.insert(
            parent,
            tk.END,
            text=node.path.name or str(node.path),
            values=(self.assignments.get(key, "—"),),
            open=open_node,
        )
        self.item_paths[item] = node.path
        for child in node.children:
            self._insert_node(item, child)
        return item

    def _on_tree_select(self, _event: object = None) -> None:
        selection = self.tree.selection()
        if not selection or self.project_root is None:
            return

        self.selected_folder = self.item_paths[selection[0]]
        self.folder_text.set(str(self.selected_folder))
        agent = self.assignments.get(
            assignment_key(self.project_root, self.selected_folder), UNASSIGNED
        )
        self.agent_text.set(agent)
        self.agent_box.configure(state="readonly")
        self._update_launch_state()
        if not self.selected_folder.is_dir():
            self.status_text.set("Folder missing. Reopen the project to refresh.")
            messagebox.showwarning(
                "Folder missing",
                "This folder no longer exists. Reopen the project to refresh the tree.",
            )

    def _on_agent_changed(self, _event: object = None) -> None:
        if self.project_root is None or self.selected_folder is None:
            return

        key = assignment_key(self.project_root, self.selected_folder)
        previous = dict(self.assignments)
        agent = self.agent_text.get()
        if agent == UNASSIGNED:
            self.assignments.pop(key, None)
        else:
            self.assignments[key] = agent

        try:
            save_assignments(self.project_root, self.assignments)
        except ConfigError as error:
            self.assignments = previous
            self.agent_text.set(previous.get(key, UNASSIGNED))
            messagebox.showerror("Cannot save assignment", str(error))
            return

        selected_item = self.tree.selection()[0]
        self.tree.set(selected_item, "agent", self.assignments.get(key, "—"))
        self.status_text.set(f"Saved {self.selected_folder.name}: {agent}")
        self._update_launch_state()

    def _update_launch_state(self) -> None:
        state = (
            "normal"
            if self.selected_folder is not None
            and can_launch(AGENT_COMMANDS.get(self.agent_text.get()), self.selected_folder)
            else "disabled"
        )
        self.launch_button.configure(state=state)

    def _open_terminal(self) -> None:
        if self.selected_folder is None:
            return
        try:
            launch_agent(self.selected_folder, AGENT_COMMANDS[self.agent_text.get()])
        except LaunchError as error:
            messagebox.showerror("Cannot open terminal", str(error))
            return
        self.status_text.set(
            f"Opened {self.agent_text.get()} in {self.selected_folder.name}"
        )


def main() -> None:
    root = tk.Tk()
    HarnessDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
