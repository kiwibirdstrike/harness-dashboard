from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from harness.agent_registry import ACCENT_COLORS, Agent, AgentRegistry, RegistryError
from harness.widgets import fallback_initial


def validate_form(name: str, command: str, color: str) -> tuple[str, str, str]:
    name = name.strip()
    command = command.strip()
    if not name or any(character in name for character in "\r\n\0"):
        raise RegistryError("Agent name is required")
    if not command or any(character in command for character in "\r\n\0"):
        raise RegistryError("Launch command must be one line")
    if color not in ACCENT_COLORS:
        raise RegistryError("Choose an accent color")
    return name, command, color


class AgentSettingsWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        registry: AgentRegistry,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.registry = registry
        self.on_change = on_change
        self.agents: list[Agent] = []
        self.selected_id: str | None = None
        self.selected_image: Path | None = None
        self._preview_photo: tk.PhotoImage | None = None
        self._warned_image: Path | None = None

        self.name_text = tk.StringVar()
        self.command_text = tk.StringVar()
        self.description_text = tk.StringVar()
        self.color_text = tk.StringVar(value=ACCENT_COLORS[0])
        self.image_text = tk.StringVar(value="No signature image")

        self.title("Manage Agents")
        self.geometry("780x550")
        self.minsize(700, 500)
        self.configure(background="#F4F7FB")
        self.transient(parent)
        self.grab_set()
        self._build()
        self._refresh()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        tk.Label(
            self,
            text="Agent Registry",
            background="#F4F7FB",
            foreground="#172033",
            font=("TkDefaultFont", 20, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=24, pady=(22, 16))

        left = tk.Frame(self, background="#FFFFFF", padx=14, pady=14)
        left.grid(row=1, column=0, sticky="nsew", padx=(24, 10), pady=(0, 24))
        left.rowconfigure(0, weight=1)
        self.agent_list = tk.Listbox(
            left,
            width=24,
            background="#FFFFFF",
            foreground="#344158",
            selectbackground="#EBE8FF",
            selectforeground="#172033",
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            font=("TkDefaultFont", 11),
        )
        self.agent_list.grid(row=0, column=0, sticky="nsew")
        self.agent_list.bind("<<ListboxSelect>>", self._select_agent)
        ttk.Button(left, text="+ New Agent", command=self._new).grid(
            row=1, column=0, sticky="ew", pady=(12, 0)
        )

        form = tk.Frame(self, background="#FFFFFF", padx=22, pady=18)
        form.grid(row=1, column=1, sticky="nsew", padx=(0, 24), pady=(0, 24))
        form.columnconfigure(1, weight=1)
        for row, label in enumerate(("Name", "Launch command", "Best for", "Accent")):
            tk.Label(
                form,
                text=label,
                background="#FFFFFF",
                foreground="#718096",
                anchor="w",
            ).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=8)
        ttk.Entry(form, textvariable=self.name_text).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Entry(form, textvariable=self.command_text).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Entry(form, textvariable=self.description_text).grid(
            row=2, column=1, sticky="ew", pady=8
        )
        ttk.Combobox(
            form,
            textvariable=self.color_text,
            values=ACCENT_COLORS,
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", pady=8)

        self.preview = tk.Canvas(
            form,
            width=88,
            height=88,
            background="#F2F5FA",
            highlightthickness=0,
        )
        self.preview.grid(row=4, column=0, rowspan=2, pady=(18, 10))
        ttk.Button(form, text="Choose PNG", command=self._choose_image).grid(
            row=4, column=1, sticky="w", pady=(18, 4)
        )
        ttk.Button(form, text="Remove Image", command=self._remove_image).grid(
            row=5, column=1, sticky="w", pady=4
        )
        tk.Label(
            form,
            textvariable=self.image_text,
            background="#FFFFFF",
            foreground="#71839F",
            anchor="w",
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(4, 14))

        actions = tk.Frame(form, background="#FFFFFF")
        actions.grid(row=7, column=0, columnspan=2, sticky="sew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        self.delete_button = ttk.Button(actions, text="Delete", command=self._delete)
        self.delete_button.grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Save Agent", command=self._save).grid(row=0, column=1)

    def _refresh(self, select_id: str | None = None) -> None:
        try:
            self.agents = self.registry.load()
        except RegistryError as error:
            messagebox.showerror("Cannot load agents", str(error), parent=self)
            return
        self.agent_list.delete(0, tk.END)
        for agent in self.agents:
            self.agent_list.insert(tk.END, agent.name)
        if select_id:
            index = next((i for i, agent in enumerate(self.agents) if agent.id == select_id), None)
            if index is not None:
                self.agent_list.selection_set(index)
                self.agent_list.event_generate("<<ListboxSelect>>")
                return
        self._new()

    def _select_agent(self, _event: object = None) -> None:
        selection = self.agent_list.curselection()
        if not selection:
            return
        agent = self.agents[selection[0]]
        self.selected_id = agent.id
        self.name_text.set(agent.name)
        self.command_text.set(agent.command)
        self.description_text.set(agent.description)
        self.color_text.set(agent.color)
        self.selected_image = self.registry.root / agent.image if agent.image else None
        self.image_text.set(agent.image or "No signature image")
        self.delete_button.grid()
        self._draw_preview()

    def _new(self) -> None:
        self.agent_list.selection_clear(0, tk.END)
        self.selected_id = None
        self.selected_image = None
        self.name_text.set("")
        self.command_text.set("")
        self.description_text.set("")
        self.color_text.set(ACCENT_COLORS[0])
        self.image_text.set("No signature image")
        self.delete_button.grid_remove()
        self._draw_preview()

    def _choose_image(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Choose a signature image",
            filetypes=[("PNG image", "*.png")],
        )
        if chosen:
            self.selected_image = Path(chosen)
            self.image_text.set(self.selected_image.name)
            self._draw_preview()

    def _remove_image(self) -> None:
        self.selected_image = None
        self.image_text.set("No signature image")
        self._draw_preview()

    def _draw_preview(self) -> None:
        self.preview.delete("all")
        self._preview_photo = None
        if self.selected_image:
            try:
                photo = tk.PhotoImage(file=str(self.selected_image))
                divisor = max(1, (max(photo.width(), photo.height()) + 71) // 72)
                self._preview_photo = photo.subsample(divisor) if divisor > 1 else photo
                self.preview.create_image(44, 44, image=self._preview_photo)
                return
            except tk.TclError:
                if self._warned_image != self.selected_image:
                    self._warned_image = self.selected_image
                    messagebox.showwarning(
                        "Cannot preview image",
                        "This PNG cannot be displayed. A letter will be used instead.",
                        parent=self,
                    )
        color = self.color_text.get() if self.color_text.get() in ACCENT_COLORS else ACCENT_COLORS[0]
        self.preview.create_text(
            44,
            44,
            text=fallback_initial(self.name_text.get()),
            fill=color,
            font=("TkDefaultFont", 28, "bold"),
        )

    def _save(self) -> None:
        try:
            name, command, color = validate_form(
                self.name_text.get(), self.command_text.get(), self.color_text.get()
            )
            if self.selected_id:
                agent = self.registry.update(
                    self.selected_id,
                    name,
                    command,
                    self.selected_image,
                    color,
                    self.description_text.get(),
                )
            else:
                agent = self.registry.add(
                    name,
                    command,
                    self.selected_image,
                    color,
                    self.description_text.get(),
                )
        except RegistryError as error:
            messagebox.showerror("Cannot save agent", str(error), parent=self)
            return
        self.on_change()
        self._refresh(agent.id)

    def _delete(self) -> None:
        if not self.selected_id or not messagebox.askyesno(
            "Delete agent?",
            "Existing project assignments will show ‘Missing agent’ until reassigned.",
            parent=self,
        ):
            return
        try:
            self.registry.delete(self.selected_id)
        except RegistryError as error:
            messagebox.showerror("Cannot delete agent", str(error), parent=self)
            return
        self.on_change()
        self._refresh()
