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
        self.status_var = tk.StringVar(value="Ready")
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

        tree_container = ttk.Frame(container)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_container,
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
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_y = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar_y.set)

        scrollbar_x = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.tree.xview)
        scrollbar_x.pack(fill=tk.X, pady=(4, 0))
        self.tree.configure(xscrollcommand=scrollbar_x.set)

        self.tree.bind("<Double-1>", lambda _: self.show_secret())
        self.tree.bind("<Return>", lambda _: self.show_secret())

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

        status_bar = ttk.Label(container, textvariable=self.status_var, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(12, 0))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _selected_item(self) -> Optional[tuple[str, str, Optional[str]]]:
        selection = self.tree.selection()
        if not selection:
            self.status_var.set("Select a secret first.")
            messagebox.showinfo("GNOMAN", "Select a secret first.")
            return None
        item_id = selection[0]
        return self._items.get(item_id)

    def refresh_secrets(self) -> None:
        """Reload keyring entries from the :class:`SecretsManager`."""

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        self._items.clear()
        self.status_var.set("Refreshing secrets…")
        try:
            records = self.manager.list(include_values=True)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Failed to list secrets: {exc}")
            self.status_var.set(f"Failed to load secrets: {exc}")
            return
        if not records:
            self.status_var.set("No secrets stored in the keyring yet.")
            return
        records.sort(key=lambda record: (record.service.casefold(), record.username.casefold()))
        for record in records:
            masked = "•" * len(record.secret or "") if record.secret else "—"
            item_id = self.tree.insert(
                "",
                tk.END,
                values=(record.service, record.username, masked),
            )
            self._items[item_id] = (record.service, record.username, record.secret)
        self.status_var.set(f"Loaded {len(records)} secret(s).")

    def show_secret(self) -> None:
        entry = self._selected_item()
        if not entry:
            return
        service, username, secret = entry
        message = (
            f"Service: {service}\nUser: {username}\n\nSecret:\n{secret or 'No value stored.'}"
        )
        messagebox.showinfo("Stored Secret", message)
        self.status_var.set(f"Displayed secret for {service}/{username}.")

    def add_secret(self) -> None:
        service = simpledialog.askstring("Add Secret", "Service namespace:", parent=self.root)
        if service is None:
            self.status_var.set("Add secret cancelled.")
            return
        if not service:
            return
        service = service.strip()
        if not service:
            messagebox.showerror("GNOMAN", "Service namespace cannot be empty.")
            self.status_var.set("Add secret cancelled: missing service namespace.")
            return
        username = simpledialog.askstring("Add Secret", "Username:", parent=self.root)
        if username is None:
            self.status_var.set("Add secret cancelled.")
            return
        if not username:
            return
        username = username.strip()
        if not username:
            messagebox.showerror("GNOMAN", "Username cannot be empty.")
            self.status_var.set("Add secret cancelled: missing username.")
            return
        secret = simpledialog.askstring(
            "Add Secret",
            "Secret value:",
            show="*",
            parent=self.root,
        )
        if secret is None:
            self.status_var.set("Add secret cancelled.")
            return
        try:
            self.manager.add(service=service, username=username, secret=secret)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Failed to store secret: {exc}")
            self.status_var.set(f"Failed to store secret: {exc}")
            return
        messagebox.showinfo("GNOMAN", f"Stored credential for {service}/{username}.")
        self.status_var.set(f"Stored credential for {service}/{username}.")
        self.refresh_secrets()

    def delete_secret(self) -> None:
        entry = self._selected_item()
        if not entry:
            return
        service, username, _ = entry
        if not messagebox.askyesno(
            "Delete Secret", f"Remove the secret for {service}/{username}?"
        ):
            self.status_var.set("Deletion cancelled.")
            return
        try:
            self.manager.delete(service=service, username=username)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Failed to delete secret: {exc}")
            self.status_var.set(f"Failed to delete secret: {exc}")
            return
        messagebox.showinfo("GNOMAN", "Secret removed.")
        self.status_var.set(f"Removed secret for {service}/{username}.")
        self.refresh_secrets()

    def rotate_secrets(self) -> None:
        service = simpledialog.askstring(
            "Rotate Secrets",
            "Restrict rotation to service (leave blank for all):",
            parent=self.root,
        )
        if service is None:
            self.status_var.set("Rotation cancelled.")
            return
        length = simpledialog.askinteger(
            "Rotate Secrets",
            "Generated secret length:",
            initialvalue=32,
            minvalue=8,
            parent=self.root,
        )
        if length is None:
            self.status_var.set("Rotation cancelled.")
            return
        services = [service.strip()] if service and service.strip() else None
        try:
            updated = self.manager.rotate(services=services, length=length)
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("GNOMAN", f"Rotation failed: {exc}")
            self.status_var.set(f"Rotation failed: {exc}")
            return
        messagebox.showinfo("GNOMAN", f"Rotated {updated} secret(s).")
        if services:
            self.status_var.set(
                f"Rotated {updated} secret(s) in namespace '{services[0]}'."
            )
        else:
            self.status_var.set(f"Rotated {updated} secret(s) across all namespaces.")
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
