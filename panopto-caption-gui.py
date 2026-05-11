#!/usr/bin/env python3
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk


APP_TITLE = "Panopto Offline Captions"
DEFAULT_OUTPUT_DIR = "offline-captions"
MODELS = [
    ("Balanced quality (base.en)", "base.en"),
    ("Faster, lower quality (tiny.en)", "tiny.en"),
    ("Better, slower (small.en)", "small.en"),
    ("Best, much slower (medium.en)", "medium.en"),
]
MODEL_VALUES = dict(MODELS)
BROWSERS = [
    ("Auto / default", ""),
    ("Chrome", "chrome"),
    ("Edge", "edge"),
    ("Firefox", "firefox"),
    ("Vivaldi", "vivaldi"),
    ("Vivaldi + GNOME Keyring", "vivaldi+gnomekeyring"),
    ("Brave", "brave"),
]
BROWSER_VALUES = dict(BROWSERS)


class CaptionApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("820x640")
        self.minsize(720, 560)

        self.repo_dir = Path(__file__).resolve().parent
        self.worker = None
        self.process = None
        self.log_queue = queue.Queue()
        self.last_output_dir = self.repo_dir / DEFAULT_OUTPUT_DIR

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(self.last_output_dir))
        self.model_var = tk.StringVar(value=MODELS[0][0])
        self.browser_var = tk.StringVar(value=self.default_browser_label())
        self.open_when_done_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")

        self.create_widgets()
        self.after(100, self.poll_log_queue)

    def create_widgets(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        title = ttk.Label(outer, text=APP_TITLE, font=("", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            outer,
            text="Download a Panopto recording, generate subtitles from the whole video, and open it in a normal player.",
            wraplength=760,
        )
        subtitle.grid(row=1, column=0, sticky="ew", pady=(4, 16))

        form = ttk.Frame(outer)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Panopto URL or video file").grid(row=0, column=0, sticky="w", pady=4)
        input_row = ttk.Frame(form)
        input_row.grid(row=0, column=1, sticky="ew", pady=4)
        input_row.columnconfigure(0, weight=1)
        ttk.Entry(input_row, textvariable=self.input_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(input_row, text="Choose File", command=self.choose_video).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(form, text="Output folder").grid(row=1, column=0, sticky="w", pady=4)
        output_row = ttk.Frame(form)
        output_row.grid(row=1, column=1, sticky="ew", pady=4)
        output_row.columnconfigure(0, weight=1)
        ttk.Entry(output_row, textvariable=self.output_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(output_row, text="Choose Folder", command=self.choose_output_dir).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(form, text="Caption quality").grid(row=2, column=0, sticky="w", pady=4)
        model_combo = ttk.Combobox(
            form,
            textvariable=self.model_var,
            values=[label for label, _ in MODELS],
            state="readonly",
        )
        model_combo.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Panopto login browser").grid(row=3, column=0, sticky="w", pady=4)
        browser_combo = ttk.Combobox(
            form,
            textvariable=self.browser_var,
            values=[label for label, _ in BROWSERS],
            state="readonly",
        )
        browser_combo.grid(row=3, column=1, sticky="ew", pady=4)

        options = ttk.Frame(form)
        options.grid(row=4, column=1, sticky="ew", pady=(8, 4))
        ttk.Checkbutton(
            options,
            text="Open video when finished",
            variable=self.open_when_done_var,
        ).pack(side=tk.LEFT)

        buttons = ttk.Frame(outer)
        buttons.grid(row=3, column=0, sticky="ew", pady=14)
        self.start_button = ttk.Button(buttons, text="Generate Captions", command=self.start_job)
        self.start_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel_job, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="Open Output Folder", command=self.open_output_folder).pack(side=tk.RIGHT)

        log_frame = ttk.Frame(outer)
        log_frame.grid(row=4, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=18, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        status = ttk.Label(outer, textvariable=self.status_var, anchor="w")
        status.grid(row=5, column=0, sticky="ew", pady=(10, 0))

    def default_browser_label(self):
        system = platform.system().lower()
        if system == "linux":
            return "Vivaldi + GNOME Keyring"
        return "Chrome"

    def choose_video(self):
        path = filedialog.askopenfilename(
            title="Choose a downloaded lecture video",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.mov *.webm *.m4v"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.input_var.set(path)

    def choose_output_dir(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_var.set(path)

    def start_job(self):
        input_value = self.input_var.get().strip()
        if not input_value:
            messagebox.showerror(APP_TITLE, "Paste a Panopto URL or choose a video file first.")
            return

        output_dir = Path(self.output_var.get().strip() or DEFAULT_OUTPUT_DIR).expanduser()
        self.last_output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        command = [
            sys.executable,
            str(self.repo_dir / "panopto-offline-captions.py"),
            input_value,
            str(output_dir),
            "--model",
            MODEL_VALUES[self.model_var.get()],
        ]

        browser = BROWSER_VALUES[self.browser_var.get()]
        if browser:
            command.extend(["--cookies-from-browser", browser])

        if not self.open_when_done_var.get():
            command.append("--no-play")

        self.set_running(True)
        self.clear_log()
        self.append_log("$ " + " ".join(quote_command_part(part) for part in command) + "\n\n")
        self.status_var.set("Running...")

        if getattr(sys, "frozen", False):
            job = {
                "input_value": input_value,
                "output_dir": str(output_dir),
                "model": MODEL_VALUES[self.model_var.get()],
                "cookies_from_browser": browser or None,
                "no_play": not self.open_when_done_var.get(),
            }
            self.worker = threading.Thread(target=self.run_packaged_job, args=(job,), daemon=True)
        else:
            self.worker = threading.Thread(target=self.run_command, args=(command,), daemon=True)
        self.worker.start()

    def run_packaged_job(self, job):
        try:
            from caption_backend import run_offline_caption_job

            run_offline_caption_job(
                job["input_value"],
                job["output_dir"],
                model=job["model"],
                cookies_from_browser=job["cookies_from_browser"],
                no_play=job["no_play"],
                log=lambda message: self.log_queue.put(("log", message + "\n")),
            )
            self.log_queue.put(("done", "Finished successfully."))
        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(("error", str(exc)))

    def run_command(self, command):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(self.repo_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(("log", line))

            return_code = self.process.wait()
            if return_code == 0:
                self.log_queue.put(("done", "Finished successfully."))
            else:
                self.log_queue.put((
                    "error",
                    f"The caption job failed with exit code {return_code}. Check the log above for the specific error.",
                ))
        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(("error", str(exc)))
        finally:
            self.process = None

    def cancel_job(self):
        if self.process and self.process.poll() is None:
            self.append_log("\nCancelling...\n")
            self.process.terminate()

    def poll_log_queue(self):
        try:
            while True:
                message_type, message = self.log_queue.get_nowait()
                if message_type == "log":
                    self.append_log(message)
                elif message_type == "done":
                    self.append_log("\n" + message + "\n")
                    self.status_var.set(message)
                    self.set_running(False)
                    messagebox.showinfo(APP_TITLE, message)
                elif message_type == "error":
                    self.append_log("\n" + message + "\n")
                    self.status_var.set(message)
                    self.set_running(False)
                    messagebox.showerror(APP_TITLE, message)
        except queue.Empty:
            pass
        self.after(100, self.poll_log_queue)

    def append_log(self, text):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def set_running(self, running):
        self.start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.cancel_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def open_output_folder(self):
        path = Path(self.output_var.get().strip() or self.last_output_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        open_path(path)


def quote_command_part(value):
    if not value or any(char.isspace() for char in value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def open_path(path):
    system = platform.system().lower()
    if system == "windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(path)])
        else:
            messagebox.showinfo(APP_TITLE, f"Output folder: {path}")


def main():
    app = CaptionApp()
    app.mainloop()


if __name__ == "__main__":
    main()
