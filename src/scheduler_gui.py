"""
GUI for creating and managing scheduled backups.
"""

import uuid
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from scheduler import (
    BackupSchedule,
    add_schedule,
    load_schedules,
    remove_schedule,
)
from windows_scheduler import create_task, remove_task


class SchedulerWindow:
    """Window for creating, viewing, and removing backup schedules."""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Scheduled Backups")
        self.window.geometry("950x600")
        self.window.minsize(800, 500)

        self.bg_color = "#1e1e1e"
        self.card_bg = "#2d2d2d"
        self.fg_color = "#ffffff"
        self.fg_muted = "#aaaaaa"
        self.accent_color = "#007acc"
        self.border_color = "#3d3d3d"

        self.window.configure(bg=self.bg_color)

        self.create_widgets()
        self.refresh_schedules()

    def create_widgets(self):
        """Create all widgets in the scheduler window."""

        main = tk.Frame(
            self.window,
            bg=self.bg_color,
            padx=15,
            pady=15,
        )
        main.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(
            main,
            text="Scheduled Backups",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Segoe UI", 15, "bold"),
        )
        title.pack(anchor=tk.W, pady=(0, 12))

        # ---------------------------------------------------------
        # Schedule configuration
        # ---------------------------------------------------------

        config_card = tk.Frame(
            main,
            bg=self.card_bg,
            highlightthickness=1,
            highlightbackground=self.border_color,
            padx=12,
            pady=12,
        )
        config_card.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            config_card,
            text="Create New Schedule",
            bg=self.card_bg,
            fg=self.fg_color,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

        # Source
        tk.Label(
            config_card,
            text="Source:",
            bg=self.card_bg,
            fg=self.fg_color,
        ).grid(row=1, column=0, sticky=tk.W, pady=5)

        self.source_var = tk.StringVar()

        tk.Entry(
            config_card,
            textvariable=self.source_var,
            bg=self.bg_color,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief="flat",
        ).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=5)

        tk.Button(
            config_card,
            text="Browse",
            command=self.browse_source,
        ).grid(row=1, column=2, pady=5)

        # Target
        tk.Label(
            config_card,
            text="Target:",
            bg=self.card_bg,
            fg=self.fg_color,
        ).grid(row=2, column=0, sticky=tk.W, pady=5)

        self.target_var = tk.StringVar()

        tk.Entry(
            config_card,
            textvariable=self.target_var,
            bg=self.bg_color,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief="flat",
        ).grid(row=2, column=1, sticky=tk.EW, padx=8, pady=5)

        tk.Button(
            config_card,
            text="Browse",
            command=self.browse_target,
        ).grid(row=2, column=2, pady=5)

        # Schedule type
        tk.Label(
            config_card,
            text="Schedule:",
            bg=self.card_bg,
            fg=self.fg_color,
        ).grid(row=3, column=0, sticky=tk.W, pady=5)

        self.type_var = tk.StringVar(value="weekly")

        self.type_menu = ttk.Combobox(
            config_card,
            textvariable=self.type_var,
            values=("weekly", "monthly", "custom"),
            state="readonly",
            width=15,
        )
        self.type_menu.grid(row=3, column=1, sticky=tk.W, padx=8, pady=5)
        self.type_menu.bind(
            "<<ComboboxSelected>>",
            lambda event: self.update_schedule_fields(),
        )

        # Dynamic schedule fields
        self.schedule_frame = tk.Frame(
            config_card,
            bg=self.card_bg,
        )
        self.schedule_frame.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky=tk.EW,
            pady=(5, 5),
        )

        self.weekday_var = tk.StringVar(value="Monday")
        self.month_day_var = tk.StringVar(value="1")
        self.time_var = tk.StringVar(value="09:00")
        self.custom_var = tk.StringVar()

        self.update_schedule_fields()

        config_card.columnconfigure(1, weight=1)

        # Add button
        tk.Button(
            config_card,
            text="Add Schedule",
            command=self.add_new_schedule,
            bg=self.accent_color,
            fg="white",
            activebackground="#1f94e5",
            activeforeground="white",
            relief="flat",
            padx=15,
            pady=7,
        ).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky=tk.W,
            pady=(10, 0),
        )

        # ---------------------------------------------------------
        # Active schedules
        # ---------------------------------------------------------

        list_card = tk.Frame(
            main,
            bg=self.card_bg,
            highlightthickness=1,
            highlightbackground=self.border_color,
            padx=10,
            pady=10,
        )
        list_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            list_card,
            text="Active Scheduled Backups",
            bg=self.card_bg,
            fg=self.fg_color,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        columns = (
            "id",
            "type",
            "scheduled",
            "source",
            "target",
        )

        self.tree = ttk.Treeview(
            list_card,
            columns=columns,
            show="headings",
        )

        self.tree.heading("id", text="ID")
        self.tree.heading("type", text="Type")
        self.tree.heading("scheduled", text="Scheduled")
        self.tree.heading("source", text="Source")
        self.tree.heading("target", text="Target")

        self.tree.column("id", width=90)
        self.tree.column("type", width=90)
        self.tree.column("scheduled", width=180)
        self.tree.column("source", width=250)
        self.tree.column("target", width=250)

        scrollbar = ttk.Scrollbar(
            list_card,
            orient=tk.VERTICAL,
            command=self.tree.yview,
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set,
        )

        self.tree.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y,
        )

        # ---------------------------------------------------------
        # Bottom buttons
        # ---------------------------------------------------------

        button_frame = tk.Frame(
            main,
            bg=self.bg_color,
        )
        button_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            button_frame,
            text="Remove Selected",
            command=self.remove_selected,
            bg="#8b2e2e",
            fg="white",
            relief="flat",
            padx=12,
            pady=7,
        ).pack(side=tk.LEFT)

        tk.Button(
            button_frame,
            text="Refresh",
            command=self.refresh_schedules,
            relief="flat",
            padx=12,
            pady=7,
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            button_frame,
            text="Enable Windows Scheduler",
            command=self.enable_windows_scheduler,
            bg=self.accent_color,
            fg="white",
            relief="flat",
            padx=12,
            pady=7,
        ).pack(side=tk.RIGHT)

        tk.Button(
            button_frame,
            text="Disable Windows Scheduler",
            command=self.disable_windows_scheduler,
            relief="flat",
            padx=12,
            pady=7,
        ).pack(side=tk.RIGHT, padx=8)

    def update_schedule_fields(self):
        """Update fields according to the selected schedule type."""

        for widget in self.schedule_frame.winfo_children():
            widget.destroy()

        schedule_type = self.type_var.get()

        if schedule_type == "weekly":
            tk.Label(
                self.schedule_frame,
                text="Day:",
                bg=self.card_bg,
                fg=self.fg_color,
            ).pack(side=tk.LEFT)

            ttk.Combobox(
                self.schedule_frame,
                textvariable=self.weekday_var,
                values=(
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ),
                state="readonly",
                width=12,
            ).pack(side=tk.LEFT, padx=8)

            tk.Label(
                self.schedule_frame,
                text="Time (HH:MM):",
                bg=self.card_bg,
                fg=self.fg_color,
            ).pack(side=tk.LEFT, padx=(15, 5))

            tk.Entry(
                self.schedule_frame,
                textvariable=self.time_var,
                width=8,
            ).pack(side=tk.LEFT)

        elif schedule_type == "monthly":
            tk.Label(
                self.schedule_frame,
                text="Day of month:",
                bg=self.card_bg,
                fg=self.fg_color,
            ).pack(side=tk.LEFT)

            tk.Spinbox(
                self.schedule_frame,
                from_=1,
                to=31,
                textvariable=self.month_day_var,
                width=5,
            ).pack(side=tk.LEFT, padx=8)

            tk.Label(
                self.schedule_frame,
                text="Time (HH:MM):",
                bg=self.card_bg,
                fg=self.fg_color,
            ).pack(side=tk.LEFT, padx=(15, 5))

            tk.Entry(
                self.schedule_frame,
                textvariable=self.time_var,
                width=8,
            ).pack(side=tk.LEFT)

        else:
            tk.Label(
                self.schedule_frame,
                text="Date & time (YYYY-MM-DD HH:MM):",
                bg=self.card_bg,
                fg=self.fg_color,
            ).pack(side=tk.LEFT)

            tk.Entry(
                self.schedule_frame,
                textvariable=self.custom_var,
                width=20,
            ).pack(side=tk.LEFT, padx=8)

    def browse_source(self):
        """Select the source directory."""

        path = filedialog.askdirectory(
            title="Select Source Folder",
        )

        if path:
            self.source_var.set(path)

    def browse_target(self):
        """Select the target directory."""

        path = filedialog.askdirectory(
            title="Select Target Folder",
        )

        if path:
            self.target_var.set(path)

    def build_schedule_time(self):
        """Build the scheduler's stored time format."""

        schedule_type = self.type_var.get()

        time_value = self.time_var.get().strip()

        try:
            datetime.strptime(time_value, "%H:%M")
        except ValueError:
            raise ValueError("Time must use HH:MM format.")

        if schedule_type == "weekly":
            weekdays = {
                "Monday": 0,
                "Tuesday": 1,
                "Wednesday": 2,
                "Thursday": 3,
                "Friday": 4,
                "Saturday": 5,
                "Sunday": 6,
            }

            return f"{weekdays[self.weekday_var.get()]}|{time_value}"

        if schedule_type == "monthly":
            day = int(self.month_day_var.get())

            if not 1 <= day <= 31:
                raise ValueError("Day of month must be between 1 and 31.")

            return f"{day}|{time_value}"

        custom_value = self.custom_var.get().strip()

        try:
            parsed = datetime.strptime(
                custom_value,
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            raise ValueError(
                "Custom date must use YYYY-MM-DD HH:MM format."
            )

        return parsed.isoformat()

    def add_new_schedule(self):
        """Create and save a new backup schedule."""

        source = self.source_var.get().strip()
        target = self.target_var.get().strip()

        if not source:
            messagebox.showerror(
                "Error",
                "Please select a source folder.",
            )
            return

        if not target:
            messagebox.showerror(
                "Error",
                "Please select a target folder.",
            )
            return

        try:
            scheduled_time = self.build_schedule_time()
        except ValueError as error:
            messagebox.showerror(
                "Invalid Schedule",
                str(error),
            )
            return

        schedule = BackupSchedule(
            schedule_id=uuid.uuid4().hex[:8],
            schedule_type=self.type_var.get(),
            scheduled_time=scheduled_time,
            source=source,
            target=target,
        )

        add_schedule(schedule)

        self.refresh_schedules()

        messagebox.showinfo(
            "Schedule Added",
            "Backup schedule created successfully.",
        )

    def refresh_schedules(self):
        """Refresh the active schedules table."""

        for item in self.tree.get_children():
            self.tree.delete(item)

        schedules = load_schedules()

        for schedule in schedules:
            self.tree.insert(
                "",
                tk.END,
                iid=schedule.schedule_id,
                values=(
                    schedule.schedule_id,
                    schedule.schedule_type,
                    schedule.scheduled_time,
                    schedule.source,
                    schedule.target,
                ),
            )

    def remove_selected(self):
        """Remove the selected schedule."""

        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Please select a schedule first.",
            )
            return

        schedule_id = selected[0]

        confirm = messagebox.askyesno(
            "Remove Schedule",
            "Remove the selected scheduled backup?",
        )

        if not confirm:
            return

        if remove_schedule(schedule_id):
            self.refresh_schedules()
            messagebox.showinfo(
                "Removed",
                "Scheduled backup removed.",
            )

    def enable_windows_scheduler(self):
        """Register the scheduler to start when Windows logs in."""

        if create_task():
            messagebox.showinfo(
                "Windows Scheduler",
                "Backup Manager scheduler will start automatically when you log in to Windows.",
            )
        else:
            messagebox.showerror(
                "Windows Scheduler",
                "Failed to enable the Windows scheduler.",
            )

    def disable_windows_scheduler(self):
        """Remove the Windows login scheduler task."""

        if remove_task():
            messagebox.showinfo(
                "Windows Scheduler",
                "Backup Manager scheduler has been disabled.",
            )
        else:
            messagebox.showerror(
                "Windows Scheduler",
                "Failed to disable the Windows scheduler.",
            )


def open_scheduler_window(parent):
    """Open the scheduled backups window."""

    SchedulerWindow(parent)