import os
import sys
import threading
import queue
import builtins
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk  # Kept only for progressbar

# Import core modules
import BackupManager
import crypto_utils
try:
    from compression import compress_to_zip
except ImportError:
    compress_to_zip = None

# Thread-safe queue for UI communication
ui_queue = queue.Queue()

class GuiTqdm:
    """Mock tqdm class that redirects progress updates to the GUI queue."""
    def __init__(self, total=None, desc="", *args, **kwargs):
        self.total = total
        self.desc = desc
        self.current = 0
        ui_queue.put(("progress_init", {"total": total, "desc": desc}))

    def update(self, n=1):
        self.current += n
        ui_queue.put(("progress_update", {"n": n}))

    def close(self):
        ui_queue.put(("progress_close", {}))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Monkeypatch tqdm globally for backup execution threads
import tqdm
tqdm.tqdm = GuiTqdm
BackupManager.tqdm_.tqdm = GuiTqdm

class BackupGuiApp:
    def __init__(self, root, args=None):
        self.root = root
        self.args = args
        self.root.title(f"Backup Manager v{BackupManager.VERSION}")
        self.root.geometry("750x650")
        self.root.minsize(650, 550)

        # Style colors
        self.bg_color = "#1e1e1e"
        self.card_bg = "#2d2d2d"
        self.fg_color = "#ffffff"
        self.fg_muted = "#888888"
        self.accent_color = "#007acc"
        self.accent_hover = "#1f94e5"
        self.border_color = "#3d3d3d"
        self.console_bg = "#121212"
        self.console_fg = "#d4d4d4"
        self.disabled_bg = "#252525"

        # Configure root style
        self.root.configure(bg=self.bg_color)
        
        # Style standard progress bar via ttk
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("TProgressbar", thickness=8, troughcolor=self.card_bg, background=self.accent_color)

        # State Variables
        self.source_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.mirror_var = tk.BooleanVar(value=False)
        self.ignore_excludes_var = tk.BooleanVar(value=False)
        
        self.zip_var = tk.BooleanVar(value=False)
        self.zip_level_var = tk.IntVar(value=3)
        
        self.sevenzip_var = tk.BooleanVar(value=False)
        self.password_var = tk.StringVar()
        self.show_password_var = tk.BooleanVar(value=False)

        self.is_running = False
        self.progress_max = 0
        self.progress_current = 0

        # Pre-populate variables from CLI arguments if present
        if args:
            if args.source:
                self.source_var.set(os.path.abspath(args.source))
            if args.target:
                self.target_var.set(os.path.abspath(args.target))
            if args.mirror:
                self.mirror_var.set(True)
            if args.ignore_excludes:
                self.ignore_excludes_var.set(True)
            if args.compression is not None:
                self.zip_var.set(True)
                self.zip_level_var.set(args.compression)
            if args.sevenzip:
                self.sevenzip_var.set(True)
            if args.password:
                self.password_var.set(args.password)

        self.create_widgets()
        self.update_options_states()
        
        # Start queue checking loop
        self.root.after(100, self.process_ui_queue)

    def create_widgets(self):
        # Main padding frame
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header Title
        header_frame = tk.Frame(main_frame, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = tk.Label(header_frame, text="Backup Manager", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 14, "bold"))
        title_label.pack(side=tk.LEFT)
        
        version_label = tk.Label(header_frame, text=f"v{BackupManager.VERSION}", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 9, "bold"))
        version_label.pack(side=tk.LEFT, padx=8, pady=(4, 0))

        # --- Card 1: Directory Selection ---
        dir_card = tk.Frame(main_frame, bg=self.card_bg, highlightthickness=1, highlightbackground=self.border_color, padx=12, pady=12)
        dir_card.pack(fill=tk.X, pady=(0, 10))

        # Source directory
        source_label = tk.Label(dir_card, text="Source Folder:", bg=self.card_bg, fg=self.fg_color, font=("Segoe UI", 10, "bold"))
        source_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        
        source_entry = tk.Entry(
            dir_card, 
            textvariable=self.source_var, 
            bg=self.bg_color, 
            fg=self.fg_color, 
            insertbackground=self.fg_color,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.accent_color,
            font=("Segoe UI", 10)
        )
        source_entry.grid(row=1, column=0, sticky=tk.EW, padx=(0, 8), pady=(0, 10))
        
        source_btn = self.create_flat_button(dir_card, "Browse...", self.browse_source)
        source_btn.grid(row=1, column=1, sticky=tk.E, pady=(0, 10))

        # Target directory
        target_label = tk.Label(dir_card, text="Target Folder / Archive Location:", bg=self.card_bg, fg=self.fg_color, font=("Segoe UI", 10, "bold"))
        target_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 4))
        
        target_entry = tk.Entry(
            dir_card, 
            textvariable=self.target_var, 
            bg=self.bg_color, 
            fg=self.fg_color, 
            insertbackground=self.fg_color,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.accent_color,
            font=("Segoe UI", 10)
        )
        target_entry.grid(row=3, column=0, sticky=tk.EW, padx=(0, 8))
        
        target_btn = self.create_flat_button(dir_card, "Browse...", self.browse_target)
        target_btn.grid(row=3, column=1, sticky=tk.E)
        
        dir_card.columnconfigure(0, weight=1)

        # --- Card 2: Backup Options Grid ---
        options_frame = tk.Frame(main_frame, bg=self.bg_color)
        options_frame.pack(fill=tk.X, pady=(0, 10))

        # Left Column: General Options
        general_card = tk.Frame(options_frame, bg=self.card_bg, highlightthickness=1, highlightbackground=self.border_color, padx=12, pady=12)
        general_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        title_general = tk.Label(general_card, text="General Options", bg=self.card_bg, fg=self.fg_color, font=("Segoe UI", 10, "bold"))
        title_general.pack(anchor=tk.W, pady=(0, 8))

        self.chk_mirror = tk.Checkbutton(
            general_card, 
            text="Mirror Mode (Delete target extra files)", 
            variable=self.mirror_var, 
            command=self.update_options_states,
            bg=self.card_bg,
            fg=self.fg_color,
            activebackground=self.card_bg,
            activeforeground=self.fg_color,
            selectcolor=self.bg_color,
            relief="flat",
            bd=0,
            cursor="hand2"
        )
        self.chk_mirror.pack(anchor=tk.W, pady=4)
        
        self.chk_ignore = tk.Checkbutton(
            general_card, 
            text="Ignore Excludes List (Copy all files)", 
            variable=self.ignore_excludes_var, 
            command=self.update_options_states,
            bg=self.card_bg,
            fg=self.fg_color,
            activebackground=self.card_bg,
            activeforeground=self.fg_color,
            selectcolor=self.bg_color,
            relief="flat",
            bd=0,
            cursor="hand2"
        )
        self.chk_ignore.pack(anchor=tk.W, pady=4)

        # Right Column: Compression / Security Options
        compression_card = tk.Frame(options_frame, bg=self.card_bg, highlightthickness=1, highlightbackground=self.border_color, padx=12, pady=12)
        compression_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        title_compress = tk.Label(compression_card, text="Format & Encryption", bg=self.card_bg, fg=self.fg_color, font=("Segoe UI", 10, "bold"))
        title_compress.pack(anchor=tk.W, pady=(0, 8))

        # Zip Mode
        self.chk_zip = tk.Checkbutton(
            compression_card, 
            text="ZIP Compression Backup", 
            variable=self.zip_var, 
            command=self.update_options_states,
            bg=self.card_bg,
            fg=self.fg_color,
            activebackground=self.card_bg,
            activeforeground=self.fg_color,
            selectcolor=self.bg_color,
            relief="flat",
            bd=0,
            cursor="hand2"
        )
        self.chk_zip.pack(anchor=tk.W, pady=2)

        # Zip Level Sub-frame
        self.zip_level_frame = tk.Frame(compression_card, bg=self.card_bg)
        self.zip_level_frame.pack(fill=tk.X, padx=20, pady=(2, 6))
        self.lbl_zip_level = tk.Label(self.zip_level_frame, text="Compression Level: 3", bg=self.card_bg, fg=self.fg_muted, font=("Segoe UI", 9))
        self.lbl_zip_level.pack(side=tk.LEFT)
        self.slider_zip = tk.Scale(
            self.zip_level_frame, 
            from_=0, 
            to=9, 
            variable=self.zip_level_var, 
            orient=tk.HORIZONTAL, 
            bg=self.card_bg, 
            fg=self.fg_color, 
            troughcolor=self.bg_color, 
            activebackground=self.accent_color, 
            relief="flat", 
            bd=0, 
            showvalue=False, 
            command=self.update_zip_label,
            highlightthickness=0,
            cursor="hand2"
        )
        self.slider_zip.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0))

        # 7z Encrypted Mode
        self.chk_sevenzip = tk.Checkbutton(
            compression_card, 
            text="7z Encrypted Archive", 
            variable=self.sevenzip_var, 
            command=self.update_options_states,
            bg=self.card_bg,
            fg=self.fg_color,
            activebackground=self.card_bg,
            activeforeground=self.fg_color,
            selectcolor=self.bg_color,
            relief="flat",
            bd=0,
            cursor="hand2"
        )
        self.chk_sevenzip.pack(anchor=tk.W, pady=2)

        # Password Entry Sub-frame
        self.pass_frame = tk.Frame(compression_card, bg=self.card_bg)
        self.pass_frame.pack(fill=tk.X, padx=20, pady=(2, 2))
        
        self.lbl_pass = tk.Label(self.pass_frame, text="Password:", bg=self.card_bg, fg=self.fg_muted, font=("Segoe UI", 9))
        self.lbl_pass.pack(side=tk.LEFT)
        
        self.entry_pass = tk.Entry(
            self.pass_frame, 
            textvariable=self.password_var, 
            show="*", 
            bg=self.bg_color, 
            fg=self.fg_color, 
            insertbackground=self.fg_color,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.accent_color,
            font=("Segoe UI", 9)
        )
        self.entry_pass.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        
        self.chk_show_pass = tk.Checkbutton(
            self.pass_frame, 
            text="Show", 
            variable=self.show_password_var, 
            command=self.toggle_password_visibility,
            bg=self.card_bg,
            fg=self.fg_color,
            activebackground=self.card_bg,
            activeforeground=self.fg_color,
            selectcolor=self.bg_color,
            relief="flat",
            bd=0,
            cursor="hand2"
        )
        self.chk_show_pass.pack(side=tk.RIGHT)

        # --- Actions Frame ---
        actions_frame = tk.Frame(main_frame, bg=self.bg_color)
        actions_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        self.btn_update = self.create_flat_button(
            actions_frame, 
            "Check for Updates", 
            self.run_update_check, 
            bg="#3a3a3a", 
            active_bg="#4a4a4a"
        )
        self.btn_update.pack(side=tk.LEFT)

        self.btn_start = self.create_flat_button(
            actions_frame, 
            "Start Backup", 
            self.start_backup_process, 
            bg=self.accent_color, 
            active_bg=self.accent_hover
        )
        self.btn_start.pack(side=tk.RIGHT)

        # --- Card 3: Log Console & Progress ---
        console_card = tk.Frame(main_frame, bg=self.card_bg, highlightthickness=1, highlightbackground=self.border_color, padx=10, pady=10)
        console_card.pack(fill=tk.BOTH, expand=True)

        # Progress Status Info
        progress_info_frame = tk.Frame(console_card, bg=self.card_bg)
        progress_info_frame.pack(fill=tk.X, pady=(0, 4))
        
        self.lbl_status = tk.Label(progress_info_frame, text="Ready", bg=self.card_bg, fg=self.fg_color, font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side=tk.LEFT)
        
        self.lbl_percent = tk.Label(progress_info_frame, text="", bg=self.card_bg, fg=self.fg_color, font=("Segoe UI", 9))
        self.lbl_percent.pack(side=tk.RIGHT)

        # Progress Bar
        self.progress_bar = ttk.Progressbar(console_card, style="TProgressbar", mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        # Scrolled Text log Console
        self.console = scrolledtext.ScrolledText(
            console_card,
            bg=self.console_bg,
            fg=self.console_fg,
            insertbackground=self.fg_color,
            font=("Consolas", 9),
            relief="flat",
            bd=0
        )
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.tag_config("info", foreground=self.console_fg)
        self.console.tag_config("warning", foreground="#e7c06d")
        self.console.tag_config("error", foreground="#f44336")
        self.console.tag_config("success", foreground="#4caf50")
        self.console.tag_config("header", foreground=self.accent_color, font=("Consolas", 9, "bold"))

    def create_flat_button(self, master, text, command, bg="#333333", active_bg="#444444"):
        btn = tk.Button(
            master,
            text=text,
            command=command,
            bg=bg,
            fg="white",
            activebackground=active_bg,
            activeforeground="white",
            bd=0,
            relief="flat",
            padx=15,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        )
        # Add subtle hover border/transition effect
        def on_enter(e):
            if btn["state"] != "disabled":
                btn.config(bg=active_bg)
        def on_leave(e):
            if btn["state"] != "disabled":
                btn.config(bg=bg)
            
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def update_zip_label(self, val):
        self.lbl_zip_level.config(text=f"Compression Level: {int(float(val))}")

    def toggle_password_visibility(self):
        if self.show_password_var.get():
            self.entry_pass.config(show="")
        else:
            self.entry_pass.config(show="*")

    def browse_source(self):
        path = filedialog.askdirectory(title="Select Source Folder")
        if path:
            self.source_var.set(os.path.normpath(path))

    def browse_target(self):
        if self.sevenzip_var.get():
            path = filedialog.asksaveasfilename(
                title="Select Encrypted Archive File",
                defaultextension=".7z",
                filetypes=[("7z Archives", "*.7z"), ("All Files", "*.*")]
            )
            if path:
                self.target_var.set(os.path.normpath(path))
        elif self.zip_var.get():
            path = filedialog.asksaveasfilename(
                title="Select Compressed ZIP File",
                defaultextension=".zip",
                filetypes=[("ZIP Archives", "*.zip"), ("All Files", "*.*")]
            )
            if path:
                self.target_var.set(os.path.normpath(path))
        else:
            path = filedialog.askdirectory(title="Select Target Folder")
            if path:
                self.target_var.set(os.path.normpath(path))

    def update_options_states(self):
        # Prevent updates/changes while task is running
        if self.is_running:
            return

        # 7z Encrypted Archive logic
        if self.sevenzip_var.get():
            # 7z is incompatible with mirror and normal zip compression
            self.mirror_var.set(False)
            self.zip_var.set(False)
            
            # Disable incompatibles
            self.chk_mirror.config(state="disabled", fg=self.fg_muted)
            self.chk_zip.config(state="disabled", fg=self.fg_muted)
            
            # Enable password options
            self.entry_pass.config(state="normal", bg=self.bg_color, fg=self.fg_color)
            self.chk_show_pass.config(state="normal", fg=self.fg_color)
            self.lbl_pass.config(fg=self.fg_color)
        else:
            # Enable options
            self.chk_mirror.config(state="normal", fg=self.fg_color)
            self.chk_zip.config(state="normal", fg=self.fg_color)
            
            # Disable password options
            self.entry_pass.config(state="disabled", bg=self.disabled_bg, fg=self.fg_muted)
            self.chk_show_pass.config(state="disabled", fg=self.fg_muted)
            self.lbl_pass.config(fg=self.fg_muted)

        # ZIP Compression logic
        if self.zip_var.get():
            self.sevenzip_var.set(False)
            self.chk_sevenzip.config(state="disabled", fg=self.fg_muted)
            
            # Enable slider
            self.slider_zip.config(state="normal", fg=self.fg_color, activebackground=self.accent_color)
            self.lbl_zip_level.config(fg=self.fg_color)
        else:
            if not self.sevenzip_var.get():
                self.chk_sevenzip.config(state="normal", fg=self.fg_color)
            
            # Disable slider
            self.slider_zip.config(state="disabled", fg=self.fg_muted, activebackground=self.disabled_bg)
            self.lbl_zip_level.config(fg=self.fg_muted)

        # Mirror mode compatibility with excludes list is kept
        if self.mirror_var.get():
            self.sevenzip_var.set(False)
            self.chk_sevenzip.config(state="disabled", fg=self.fg_muted)
            
            # Mirror is incompatible with ignore-excludes
            self.ignore_excludes_var.set(False)
            self.chk_ignore.config(state="disabled", fg=self.fg_muted)
        else:
            if not self.sevenzip_var.get():
                self.chk_sevenzip.config(state="normal", fg=self.fg_color)
            self.chk_ignore.config(state="normal", fg=self.fg_color)

    def log_message(self, message, tag="info"):
        self.console.config(state="normal")
        
        # Check if line contains tags
        tag_to_use = tag
        if "ERROR:" in message:
            tag_to_use = "error"
        elif "WARNING:" in message:
            tag_to_use = "warning"
        elif "success" in message.lower() or "completed" in message.lower() or "finished" in message.lower():
            tag_to_use = "success"
        elif message.startswith("==="):
            tag_to_use = "header"

        self.console.insert(tk.END, message + "\n", tag_to_use)
        self.console.config(state="disabled")
        self.console.see(tk.END)

    def set_gui_state(self, enabled):
        state_val = "normal" if enabled else "disabled"
        self.btn_start.config(state=state_val)
        self.btn_update.config(state=state_val)
        
        # Lock fields
        state_entry = "normal" if enabled else "disabled"
        self.chk_mirror.config(state=state_entry)
        self.chk_ignore.config(state=state_entry)
        self.chk_zip.config(state=state_entry)
        self.slider_zip.config(state=state_entry)
        self.chk_sevenzip.config(state=state_entry)
        self.entry_pass.config(state=state_entry)
        self.chk_show_pass.config(state=state_entry)
        
        if enabled:
            self.update_options_states()
        else:
            self.chk_mirror.config(fg=self.fg_muted)
            self.chk_ignore.config(fg=self.fg_muted)
            self.chk_zip.config(fg=self.fg_muted)
            self.slider_zip.config(fg=self.fg_muted)
            self.chk_sevenzip.config(fg=self.fg_muted)
            self.entry_pass.config(bg=self.disabled_bg, fg=self.fg_muted)
            self.chk_show_pass.config(fg=self.fg_muted)
            self.lbl_pass.config(fg=self.fg_muted)
            self.lbl_zip_level.config(fg=self.fg_muted)

    def run_update_check(self):
        self.set_gui_state(False)
        self.lbl_status.config(text="Checking for updates...", fg=self.fg_color)
        self.log_message("=== Checking dependencies & updates ===")
        
        def task():
            try:
                # Run check
                release = BackupManager.check_for_update()
                current = BackupManager.get_current_version()
                
                if release and BackupManager.compare_versions(current, release['version']):
                    ui_queue.put(("update_available", release))
                else:
                    ui_queue.put(("update_none", {}))
            except Exception as e:
                ui_queue.put(("log", f"ERROR: Update check failed: {e}"))
                ui_queue.put(("update_done", {}))

        threading.Thread(target=task, daemon=True).start()

    def start_backup_process(self):
        source = self.source_var.get().strip()
        target = self.target_var.get().strip()

        # Input validations
        if not source:
            messagebox.showerror("Error", "Please select a Source Folder.")
            return
        if not target:
            messagebox.showerror("Error", "Please select a Target Folder / Archive Location.")
            return
        if not os.path.exists(source):
            messagebox.showerror("Error", f"Source folder does not exist:\n{source}")
            return
        if source == target:
            messagebox.showerror("Error", "Source and Target cannot be the same folder.")
            return

        # Double check 7z details
        if self.sevenzip_var.get():
            if not self.password_var.get():
                messagebox.showerror("Error", "Password is required for 7z Encrypted Archive.")
                return
            # Ensure target path has .7z extension if not already
            if not target.lower().endswith(".7z"):
                target += ".7z"
                self.target_var.set(target)

        # Clear logs and reset progress
        self.console.config(state="normal")
        self.console.delete("1.0", tk.END)
        self.console.config(state="disabled")
        
        self.is_running = True
        self.set_gui_state(False)
        self.progress_bar["value"] = 0
        self.lbl_percent.config(text="")
        
        # Configure globals in BackupManager
        BackupManager.IGNORE_EXCLUDE_LIST = self.ignore_excludes_var.get()
        BackupManager.MIRROR_MODE = self.mirror_var.get()

        # Intercept output
        BackupManager.log = lambda msg: ui_queue.put(("log", msg))
        
        # Thread-safe prompt interceptor using queue
        def gui_input(prompt_text):
            res_queue = queue.Queue()
            ui_queue.put(("prompt", (prompt_text, res_queue)))
            return res_queue.get()
        
        builtins.input = gui_input

        # Start backup thread
        threading.Thread(target=self.backup_worker, args=(source, target), daemon=True).start()

    def backup_worker(self, source, target):
        success = False
        start_time = time.time()
        
        try:
            # 7z Encrypted archive path
            if self.sevenzip_var.get():
                ui_queue.put(("log", "=== Initializing 7z encrypted backup ==="))
                ui_queue.put(("log", f"Source: {source}"))
                ui_queue.put(("log", f"Archive file: {target}"))
                
                # Make parent folder
                parent = os.path.dirname(target)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                
                success = crypto_utils.encrypt_directory_7z(
                    source_dir=source,
                    output_file=target,
                    password=self.password_var.get(),
                    log_func=lambda msg: ui_queue.put(("log", msg))
                )
                
                if success:
                    ui_queue.put(("log", f"Backup completed successfully: {target}"))
                else:
                    ui_queue.put(("log", "ERROR: Backup failed"))
                    
            # ZIP Compression path
            elif self.zip_var.get():
                ui_queue.put(("log", "=== Initializing ZIP compression backup ==="))
                ui_queue.put(("log", f"Source: {source}"))
                ui_queue.put(("log", f"Archive file: {target}"))
                
                if not compress_to_zip:
                    ui_queue.put(("log", "ERROR: compression.py could not be loaded"))
                else:
                    # Make parent folder if file path
                    if target.lower().endswith(".zip"):
                        parent = os.path.dirname(target)
                        if parent:
                            os.makedirs(parent, exist_ok=True)
                            
                    success = compress_to_zip(
                        source,
                        target,
                        compression_level=self.zip_level_var.get(),
                        log_func=lambda msg: ui_queue.put(("log", msg)),
                        should_ignore_func=BackupManager.should_ignore,
                        num_threads=BackupManager.THREADS
                    )
            
            # Normal Backup path
            else:
                # Run main logic
                BackupManager.main(source_dir=source, target_dir=target)
                success = True
                
        except Exception as e:
            ui_queue.put(("log", f"ERROR: Unexpected thread failure: {e}"))
            
        finally:
            elapsed = time.time() - start_time
            ui_queue.put(("log", f"Time elapsed: {elapsed:.2f} seconds"))
            ui_queue.put(("backup_done", success))

    def process_ui_queue(self):
        """Processes events in the UI thread from the background worker threads."""
        try:
            while True:
                event_type, data = ui_queue.get_nowait()
                
                if event_type == "log":
                    self.log_message(data)
                    
                elif event_type == "prompt":
                    # Prompt handling: prompt_text, response_queue
                    prompt_text, res_queue = data
                    
                    # Intercept mirror deletion prompts
                    if "Mirror mode: delete" in prompt_text:
                        ans = messagebox.askyesno("Confirm Mirror Deletion", prompt_text)
                        res_queue.put("y" if ans else "n")
                    else:
                        # Any default/unhandled prompt
                        res_queue.put("")
                        
                elif event_type == "progress_init":
                    self.progress_max = data.get("total") or 0
                    self.progress_current = 0
                    self.lbl_status.config(text=data.get("desc") or "Processing...", fg=self.fg_color)
                    
                    if self.progress_max > 0:
                        self.progress_bar["mode"] = "determinate"
                        self.progress_bar["maximum"] = self.progress_max
                        self.progress_bar["value"] = 0
                    else:
                        self.progress_bar["mode"] = "indeterminate"
                        self.progress_bar.start(10)
                        
                elif event_type == "progress_update":
                    n = data.get("n") or 1
                    self.progress_current += n
                    
                    if self.progress_max > 0:
                        self.progress_bar["value"] = self.progress_current
                        percentage = (self.progress_current / self.progress_max) * 100
                        # Check units to format text nicely
                        if self.progress_max > 1024 * 1024:
                            curr_mb = self.progress_current / (1024 * 1024)
                            total_mb = self.progress_max / (1024 * 1024)
                            self.lbl_percent.config(text=f"{curr_mb:.1f} MB / {total_mb:.1f} MB ({percentage:.1f}%)")
                        elif self.progress_max > 100:
                            self.lbl_percent.config(text=f"{self.progress_current} / {self.progress_max} ({percentage:.1f}%)")
                        else:
                            self.lbl_percent.config(text=f"{percentage:.1f}%")
                            
                elif event_type == "progress_close":
                    self.progress_bar.stop()
                    self.progress_bar["mode"] = "determinate"
                    self.progress_bar["value"] = self.progress_bar["maximum"]
                    self.lbl_percent.config(text="")
                    
                elif event_type == "backup_done":
                    self.is_running = False
                    self.set_gui_state(True)
                    self.lbl_status.config(text="Finished" if data else "Failed", fg=self.fg_color)
                    if data:
                        messagebox.showinfo("Success", "Backup task completed successfully!")
                    else:
                        messagebox.showerror("Failed", "Backup task finished with errors. See logs.")
                        
                elif event_type == "update_available":
                    self.set_gui_state(True)
                    self.lbl_status.config(text="Update Available", fg=self.fg_color)
                    release_info = data
                    self.log_message(f"Update available: {release_info['version']}")
                    
                    ans = messagebox.askyesno(
                        "Update Available",
                        f"A new version v{release_info['version']} is available.\n\n"
                        f"Release Name: {release_info['release_name']}\n\n"
                        f"Do you want to download and install this update?"
                    )
                    
                    if ans:
                        self.set_gui_state(False)
                        self.lbl_status.config(text="Updating...", fg=self.fg_color)
                        self.log_message("Starting update download and installation...")
                        
                        def update_task():
                            success = BackupManager.install_update(release_info)
                            ui_queue.put(("update_done", success))
                        
                        threading.Thread(target=update_task, daemon=True).start()
                    else:
                        self.lbl_status.config(text="Ready", fg=self.fg_color)
                        
                elif event_type == "update_none":
                    self.set_gui_state(True)
                    self.lbl_status.config(text="Ready", fg=self.fg_color)
                    self.log_message("All dependencies are up to date. No updates available.")
                    messagebox.showinfo("Update Check", "Your Backup Manager is up to date!")
                    
                elif event_type == "update_done":
                    self.set_gui_state(True)
                    self.lbl_status.config(text="Ready", fg=self.fg_color)
                    if data:
                        self.log_message("Update completed successfully! Please restart the program.")
                        messagebox.showinfo("Updated", "Update installed successfully!\nPlease restart the application.")
                    else:
                        self.log_message("ERROR: Update installation failed.")
                        messagebox.showerror("Update Failed", "Failed to install the update. Please check the logs.")
                        
        except queue.Empty:
            pass
            
        # Re-register loop
        self.root.after(100, self.process_ui_queue)

def start_gui(args=None):
    root = tk.Tk()
    app = BackupGuiApp(root, args)
    root.mainloop()

if __name__ == "__main__":
    start_gui()
