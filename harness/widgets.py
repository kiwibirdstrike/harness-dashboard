from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from harness.agent_registry import Agent


def fallback_initial(name: str) -> str:
    return name.strip()[:1].upper() or "?"


def tree_row_at_pointer(tree: object, x_root: int, y_root: int) -> str:
    x = x_root - tree.winfo_rootx()
    y = y_root - tree.winfo_rooty()
    if not 0 <= x < tree.winfo_width() or not 0 <= y < tree.winfo_height():
        return ""
    return tree.identify_row(y)


class AgentCard(tk.Canvas):
    def __init__(self, master: tk.Misc, agent: Agent, image_root: Path, **kwargs: object) -> None:
        super().__init__(
            master,
            width=244,
            height=100,
            background="#F9FBFE",
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.agent_id = agent.id
        self.agent_name = agent.name
        self.agent_color = agent.color
        self._photo: tk.PhotoImage | None = None
        self._rounded_rectangle(3, 3, 241, 97, 14, fill="#FFFFFF", outline="#DDE5F0")
        self.create_line(11, 22, 11, 78, fill=agent.color, width=4, capstyle=tk.ROUND)
        self.create_oval(22, 27, 64, 69, fill="#F2F5FA", outline="")
        if not self._draw_image(agent, image_root):
            self.create_text(
                43,
                48,
                text=fallback_initial(agent.name),
                fill=agent.color,
                font=("TkDefaultFont", 14, "bold"),
            )
        self.create_text(
            76,
            22,
            text=agent.name,
            fill="#172033",
            anchor="w",
            font=("TkDefaultFont", 11, "bold"),
        )
        self.create_text(
            76,
            50,
            text=agent.description or "사용 목적을 설명에 추가하세요",
            fill="#68788F",
            anchor="w",
            width=154,
            font=("TkDefaultFont", 9),
        )
        self.create_text(
            76,
            80,
            text=agent.command,
            fill="#98A5B7",
            anchor="w",
            width=154,
            font=("TkFixedFont", 8),
        )

    def _rounded_rectangle(
        self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object
    ) -> int:
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        return self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _draw_image(self, agent: Agent, image_root: Path) -> bool:
        if not agent.image:
            return False
        try:
            photo = tk.PhotoImage(file=str(image_root / agent.image))
            divisor = max(1, (max(photo.width(), photo.height()) + 41) // 42)
            self._photo = photo.subsample(divisor) if divisor > 1 else photo
            self.create_image(43, 48, image=self._photo)
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
        self.tree.tag_configure("drag-target", background="#DDD8FF", foreground="#172033")

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
