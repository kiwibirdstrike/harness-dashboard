from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from harness.agent_registry import Agent


def fallback_initial(name: str) -> str:
    return name.strip()[:1].upper() or "?"


def tree_row_at_pointer(tree: object, x_root: int, y_root: int) -> str:
    del x_root
    return tree.identify_row(y_root - tree.winfo_rooty())


class AgentCard(tk.Canvas):
    def __init__(self, master: tk.Misc, agent: Agent, image_root: Path, **kwargs: object) -> None:
        super().__init__(
            master,
            width=210,
            height=72,
            background="#131B2E",
            highlightbackground="#263149",
            highlightthickness=1,
            cursor="hand2",
            **kwargs,
        )
        self.agent_id = agent.id
        self.agent_name = agent.name
        self.agent_color = agent.color
        self._photo: tk.PhotoImage | None = None
        self.create_rectangle(0, 0, 5, 72, fill=agent.color, outline=agent.color)
        self.create_oval(18, 18, 54, 54, fill="#202B43", outline="")
        if not self._draw_image(agent, image_root):
            self.create_text(
                36,
                36,
                text=fallback_initial(agent.name),
                fill=agent.color,
                font=("TkDefaultFont", 14, "bold"),
            )
        self.create_text(
            66,
            25,
            text=agent.name,
            fill="#F8FAFC",
            anchor="w",
            font=("TkDefaultFont", 11, "bold"),
        )
        self.create_text(
            66,
            47,
            text=agent.command,
            fill="#8EA0BC",
            anchor="w",
            width=132,
            font=("TkDefaultFont", 9),
        )

    def _draw_image(self, agent: Agent, image_root: Path) -> bool:
        if not agent.image:
            return False
        try:
            photo = tk.PhotoImage(file=str(image_root / agent.image))
            divisor = max(1, (max(photo.width(), photo.height()) + 35) // 36)
            self._photo = photo.subsample(divisor) if divisor > 1 else photo
            self.create_image(36, 36, image=self._photo)
            return True
        except tk.TclError:
            return False


class AgentDragController:
    def __init__(
        self,
        root: tk.Misc,
        tree: ttk.Treeview,
        on_drop: Callable[[str, str], None],
    ) -> None:
        self.root = root
        self.tree = tree
        self.on_drop = on_drop
        self.agent_id = ""
        self.press = (0, 0)
        self.target = ""
        self.ghost: tk.Toplevel | None = None
        self.tree.tag_configure("drag-target", background="#263B63", foreground="#FFFFFF")

    def attach(self, card: AgentCard, on_click: Callable[[str], None]) -> None:
        card.bind("<ButtonPress-1>", lambda event: self._start(card, event))
        card.bind("<B1-Motion>", self._motion)
        card.bind("<ButtonRelease-1>", lambda event: self._release(on_click, event))

    def _start(self, card: AgentCard, event: tk.Event) -> None:
        self.agent_id = card.agent_id
        self.press = (event.x_root, event.y_root)

    def _motion(self, event: tk.Event) -> None:
        if not self.agent_id:
            return
        if self.ghost is None:
            if abs(event.x_root - self.press[0]) + abs(event.y_root - self.press[1]) <= 5:
                return
            self.ghost = tk.Toplevel(self.root)
            self.ghost.overrideredirect(True)
            tk.Label(
                self.ghost,
                text="  Assign agent  ",
                background="#7C3AED",
                foreground="white",
                padx=8,
                pady=6,
            ).pack()
        self.ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        self._highlight(tree_row_at_pointer(self.tree, event.x_root, event.y_root))

    def _release(self, on_click: Callable[[str], None], event: tk.Event) -> None:
        del event
        dragged = self.ghost is not None
        target = self.target
        agent_id = self.agent_id
        self._clear()
        if dragged and target:
            self.on_drop(agent_id, target)
        elif not dragged and agent_id:
            on_click(agent_id)

    def _highlight(self, item: str) -> None:
        if item == self.target:
            return
        self._remove_target_tag(self.target)
        self.target = item
        if item:
            tags = set(self.tree.item(item, "tags"))
            self.tree.item(item, tags=(*tags, "drag-target"))

    def _remove_target_tag(self, item: str) -> None:
        if item:
            tags = tuple(tag for tag in self.tree.item(item, "tags") if tag != "drag-target")
            self.tree.item(item, tags=tags)

    def _clear(self) -> None:
        self._remove_target_tag(self.target)
        if self.ghost is not None:
            self.ghost.destroy()
        self.agent_id = ""
        self.target = ""
        self.ghost = None
