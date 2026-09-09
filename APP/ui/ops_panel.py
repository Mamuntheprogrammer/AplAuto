"""Dynamic operations panel: dropdown + auto-built parameter widgets."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from operations import ParamSpec, get_operation, list_operations
from ui.date_picker import CalendarDialog, format_de, month_last_day, parse_de_date_str


class OperationsPanel(ctk.CTkFrame):
    """Lets the user pick an operation, fill params, and press Apply."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        on_apply: Callable[[str, dict[str, Any]], None],
    ) -> None:
        super().__init__(parent, corner_radius=12, width=320)
        self._on_apply = on_apply
        self._param_widgets: dict[str, Any] = {}
        self._columns: list[str] = []

        ctk.CTkLabel(self, text="⚙ Operations", font=("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        self.op_menu = ctk.CTkOptionMenu(
            self, values=list_operations() or ["(no operations)"], command=self._rebuild_params
        )
        self.op_menu.pack(fill="x", padx=14, pady=4)
        self.desc_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 11), text_color="gray70", wraplength=280,
            justify="left",
        )
        self.desc_label.pack(anchor="w", padx=14, pady=(0, 6))

        self.params_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", height=320)
        self.params_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.apply_btn = ctk.CTkButton(
            self, text="▶ Apply Operation", fg_color="#1f6aa5",
            hover_color="#185a8d", command=self._submit,
        )
        self.apply_btn.pack(fill="x", padx=14, pady=12)
        if list_operations():
            self._rebuild_params(list_operations()[0])

    # ------------------------------------------------------------- public API
    def set_columns(self, columns: list[str]) -> None:
        """Refresh column choices then rebuild current param widgets."""
        self._columns = [str(c) for c in columns]
        self._rebuild_params(self.op_menu.get())

    def current_operation(self) -> str:
        """Selected operation display name."""
        return self.op_menu.get()

    # ---------------------------------------------------------- widget builders
    def _clear_params(self) -> None:
        for child in self.params_frame.winfo_children():
            child.destroy()
        self._param_widgets = {}

    def _rebuild_params(self, op_name: str) -> None:
        self._clear_params()
        try:
            spec = get_operation(op_name)
        except KeyError:
            return
        self.desc_label.configure(text=spec.description)
        for param in spec.params:
            self._build_param(param)

    def _build_param(self, param: ParamSpec) -> None:
        ctk.CTkLabel(self.params_frame, text=param.label, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=6, pady=(8, 2)
        )
        cols = self._columns or ["(load a file first)"]
        if param.kind == "column":
            opts = [""] + self._columns if not param.required else (self._columns or cols)
            widget = ctk.CTkOptionMenu(self.params_frame, values=opts or [""])
            widget.pack(fill="x", padx=6)
            self._param_widgets[param.name] = widget
        elif param.kind in ("operator", "select"):
            widget = ctk.CTkOptionMenu(self.params_frame, values=param.options)
            if param.default:
                widget.set(param.default)
            widget.pack(fill="x", padx=6)
            self._param_widgets[param.name] = widget
        elif param.kind in ("text", "number", "expression"):
            widget = ctk.CTkEntry(self.params_frame, placeholder_text=param.default or param.label)
            if param.default:
                widget.insert(0, param.default)
            widget.pack(fill="x", padx=6)
            self._param_widgets[param.name] = widget
        elif param.kind == "date":
            row = ctk.CTkFrame(self.params_frame, fg_color="transparent")
            row.pack(fill="x", padx=6)
            entry = ctk.CTkEntry(row, placeholder_text="DD.MM.YYYY")
            if param.default:
                entry.insert(0, param.default)
            entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkButton(
                row, text="📅", width=40,
                command=lambda n=param.name, e=entry: self._pick_date(n, e),
            ).pack(side="right")
            self._param_widgets[param.name] = entry
            if param.name == "start_date":
                entry.bind("<FocusOut>", lambda _e, e=entry: self._autofill_end(e))
                entry.bind("<Return>", lambda _e, e=entry: self._autofill_end(e))
        elif param.kind == "divisions":
            box = ctk.CTkScrollableFrame(self.params_frame, height=140)
            box.pack(fill="x", padx=6)
            var = ctk.StringVar(value="")
            for option in param.options:
                rb = ctk.CTkRadioButton(box, text=option, variable=var, value=option)
                rb.pack(anchor="w", padx=6, pady=1)
            self._param_widgets[param.name] = var
        elif param.kind == "columns":
            box = ctk.CTkScrollableFrame(self.params_frame, height=120)
            box.pack(fill="x", padx=6)
            checks: dict[str, ctk.CTkCheckBox] = {}
            for col in self._columns:
                var = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(box, text=str(col)[:30], variable=var)
                cb.pack(anchor="w", padx=6, pady=1)
                checks[col] = var
            self._param_widgets[param.name] = checks

    # ------------------------------------------------------------------ submit
    def _pick_date(self, name: str, entry: ctk.CTkEntry) -> None:
        """Open the calendar popup; picking Start auto-fills End with month-end."""
        selected = CalendarDialog.pick(self, entry.get().strip())
        if not selected:
            return
        entry.delete(0, "end")
        entry.insert(0, selected)
        if name == "start_date":
            self._autofill_end(entry, force=True)

    def _autofill_end(self, start_entry: ctk.CTkEntry, force: bool = False) -> None:
        """Set End date to the last day of Start's month."""
        end_widget = self._param_widgets.get("end_date")
        if not isinstance(end_widget, ctk.CTkEntry):
            return
        start = parse_de_date_str(start_entry.get())
        if start is None:
            return
        current = parse_de_date_str(end_widget.get())
        if force or current is None or (current.year, current.month) != (start.year, start.month):
            end_widget.delete(0, "end")
            end_widget.insert(0, format_de(month_last_day(start)))

    def _submit(self) -> None:
        op_name = self.op_menu.get()
        try:
            spec = get_operation(op_name)
        except KeyError:
            return
        params: dict[str, Any] = {}
        for param in spec.params:
            widget = self._param_widgets.get(param.name)
            if widget is None:
                continue
            if param.kind == "columns":
                params[param.name] = [c for c, v in widget.items() if v.get()]
            elif param.kind == "divisions":
                params[param.name] = widget.get() if isinstance(widget, ctk.StringVar) else ""
            elif isinstance(widget, ctk.CTkOptionMenu):
                params[param.name] = widget.get()
            elif isinstance(widget, ctk.CTkEntry):
                params[param.name] = widget.get().strip()
        self._on_apply(op_name, params)
