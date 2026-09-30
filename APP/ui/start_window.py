"""Start page (frame switched inside one window)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class StartPage(ctk.CTkFrame):
    """Launcher page with Reporting and Setup cards."""

    def __init__(
        self, master, on_open_setup: Callable[[], None],
        on_open_reporting: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_setup = on_open_setup
        self._on_reporting = on_open_reporting

        ctk.CTkLabel(
            self, text="Excel Processor", font=("Segoe UI", 26, "bold")
        ).pack(pady=(48, 4))
        ctk.CTkLabel(
            self, text="Choose a workspace to continue",
            font=("Segoe UI", 13), text_color="gray70",
        ).pack(pady=(0, 16))

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(fill="both", expand=True, padx=40, pady=(0, 30))

        cards = ctk.CTkFrame(center, fg_color="transparent")
        cards.place(relx=0.5, rely=0.5, anchor="center")
        cards.grid_columnconfigure(0, weight=0)
        cards.grid_columnconfigure(1, weight=0)

        self._make_card(
            cards, 0, icon="📊", title="Reporting",
            desc="Reports workspace.",
            button_text="Open Reporting", command=self._on_reporting,
        )
        self._make_card(
            cards, 1, icon="⚙️", title="Setup",
            desc="Import, process and export files.",
            button_text="Open Setup", command=self._on_setup, accent=True,
        )

    def _make_card(self, parent, col: int, *, icon: str, title: str,
                   desc: str, button_text: str, command, accent: bool = False) -> None:
        card = ctk.CTkFrame(
            parent, corner_radius=16, width=300, height=340,
            border_width=1,
            border_color="#1f6aa5" if accent else "#3a3a3a",
        )
        card.grid(row=0, column=col, padx=12, pady=12)
        card.pack_propagate(False)
        card.grid_propagate(False)

        ctk.CTkLabel(card, text=icon, font=("Segoe UI", 48)).pack(pady=(28, 6))
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 19, "bold")).pack()
        ctk.CTkLabel(
            card, text=desc, font=("Segoe UI", 12),
            text_color="gray70", justify="center",
        ).pack(pady=(6, 16))

        kwargs = {"fg_color": "#1f6aa5", "hover_color": "#185a8d"} if accent else {
            "fg_color": "#3a3a3a", "hover_color": "#4a4a4a"}
        ctk.CTkButton(
            card, text=button_text, width=170, height=36,
            command=command, **kwargs,  # type: ignore[arg-type]
        ).pack(pady=(0, 24))
