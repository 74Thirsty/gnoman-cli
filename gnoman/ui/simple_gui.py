"""Tkinter powered lightweight GUI for a subset of GNOMAN features."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, Optional

from ..core import SecretsManager


class SimpleGUI:
    """Expose core secret management features through a desktop window."""

    def __init__(self, *, root: Optional[tk.Tk] = None) -> None:
        self.root = root or tk.Tk()
        self.root.title("GNOMAN — Simple GUI")
        self.root.geometry("720x420")
        self.manager = SecretsManager()
        self._items: Dict[str, tuple[str, str, Optional[str]]] = {}
        self._build_layout()
        self.refresh_secrets()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        heading = ttk.Label(
            container,
            text="Secrets Vault",
            font=("TkDefaultFont", 14, "bold"),
        )
        heading.pack(anchor="w", pady=(0, 8))

        description = ttk.Label(
            container,
            text=(
                "List, add, delete or rotate credentials stored in your system keyring."
            ),
            wraplength=680,
            justify=tk.LEFT,
        )
        description.pack(anchor="w", pady=(0, 12))

        self.tree = ttk.Treeview(
            container,
            columns=("service", "username", "secret"),
            show="headings",
            height=12,
        )
        self.tree.heading("service", text="Service")
        self.tree.heading("username", text="Username")
        self.tree.heading("secret", text="Secret (masked)")
        self.tree.column("service", width=200, anchor=tk.W, stretch=True)
        self.tree.column("username", width=200, anchor=tk.W, stretch=True)
        self.tree.column("secret", width=250, anchor=tk.W, stretch=True)
        self.tree.pack(fill=tk.BOTH, expand=True)

        button_bar = ttk.Frame(container)
        button_bar.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(button_bar, text="Refresh", command=self.refresh_secrets).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(button_bar, text="Show Secret", command=self.show_secret).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(button_bar, text="Add Secret", command=self.add_secret).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(button_bar, text="Delete Secret", command=self.delete_secret).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(button_bar, text="Rotate", command=self.rotate_secrets).pack(
            side=tk.LEFT, padx=8
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _selected_item(self) -> Optional[tuple[str, str, Optional[str]]]:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("GNOMAN", "Select a secret first.")
            return None
        item_id = selection[0]
        return self._items.get(item_id)

    def refresh_secrets(self) -> None:
        """Reload keyring entries from the :class:`SecretsManager`."""

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        self._items.clear()
        try:
            records = self.manager.list(include_values=True)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Failed to list secrets: {exc}")
            return
        if not records:
            messagebox.showinfo("GNOMAN", "No secrets stored in the keyring yet.")
            return
        for record in records:
            masked = "•" * len(record.secret or "") if record.secret else "—"
            item_id = self.tree.insert(
                "",
                tk.END,
                values=(record.service, record.username, masked),
            )
            self._items[item_id] = (record.service, record.username, record.secret)

    def show_secret(self) -> None:
        entry = self._selected_item()
        if not entry:
            return
        service, username, secret = entry
        message = (
            f"Service: {service}\nUser: {username}\n\nSecret:\n{secret or 'No value stored.'}"
        )
        messagebox.showinfo("Stored Secret", message)

    def add_secret(self) -> None:
        service = simpledialog.askstring("Add Secret", "Service namespace:", parent=self.root)
        if not service:
            return
        username = simpledialog.askstring("Add Secret", "Username:", parent=self.root)
        if not username:
            return
        secret = simpledialog.askstring(
            "Add Secret",
            "Secret value:",
            show="*",
            parent=self.root,
        )
        if secret is None:
            return
        try:
            self.manager.add(service=service.strip(), username=username.strip(), secret=secret)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Failed to store secret: {exc}")
            return
        messagebox.showinfo("GNOMAN", f"Stored credential for {service}/{username}.")
        self.refresh_secrets()

    def delete_secret(self) -> None:
        entry = self._selected_item()
        if not entry:
            return
        service, username, _ = entry
        if not messagebox.askyesno(
            "Delete Secret", f"Remove the secret for {service}/{username}?"
        ):
            return
        try:
            self.manager.delete(service=service, username=username)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Failed to delete secret: {exc}")
            return
        messagebox.showinfo("GNOMAN", "Secret removed.")
        self.refresh_secrets()

    def rotate_secrets(self) -> None:
        service = simpledialog.askstring(
            "Rotate Secrets",
            "Restrict rotation to service (leave blank for all):",
            parent=self.root,
        )
        length = simpledialog.askinteger(
            "Rotate Secrets",
            "Generated secret length:",
            initialvalue=32,
            minvalue=8,
            parent=self.root,
        )
        if length is None:
            return
        services = [service.strip()] if service and service.strip() else None
        try:
            updated = self.manager.rotate(services=services, length=length)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Rotation failed: {exc}")
            return
        messagebox.showinfo("GNOMAN", f"Rotated {updated} secret(s).")
        self.refresh_secrets()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the Tkinter main loop."""

        self.root.mainloop()


def launch() -> None:
    """Helper for scripts to launch the GUI without instantiating the class."""

    SimpleGUI().run()


__all__ = ["SimpleGUI", "launch"]
