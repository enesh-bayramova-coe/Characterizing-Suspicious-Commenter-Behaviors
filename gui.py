# Tkinter-based GUI.

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from typing import List

from pipeline import run_pipeline, MAX_COMMENTS


class BotDetectionApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YouTube Bot Detection")
        self.root.geometry("820x720")
        self.root.resizable(False, False)

        self.video_id_var = tk.StringVar(value="dQw4w9WgXcQ")
        self.max_comments_var = tk.StringVar(value=str(MAX_COMMENTS))
        self.build_ui()

    def build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="YouTube Bot Detection", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(
            frame,
            text=(
                "Enter a YouTube video ID and the number of comments to analyze. "
                "The pipeline fetches up to 10000 comments and displays suspicious accounts."
            ),
            wraplength=780,
            justify=tk.LEFT,
            fg="#333"
        ).pack(anchor="w", pady=(4, 12))

        input_frame = tk.Frame(frame)
        input_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(input_frame, text="Video URL/ID:", width=12, anchor="w").grid(row=0, column=0, sticky="w")
        tk.Entry(input_frame, textvariable=self.video_id_var, width=34).grid(row=0, column=1, sticky="w")

        tk.Label(input_frame, text="Comments to fetch:", width=16, anchor="w").grid(row=1, column=0, sticky="w", pady=(8, 0))
        tk.Entry(input_frame, textvariable=self.max_comments_var, width=12).grid(row=1, column=1, sticky="w", pady=(8, 0))

        self.run_button = tk.Button(frame, text="Run Pipeline", width=16, command=self.start_pipeline)
        self.run_button.pack(anchor="w", pady=(0, 12))

        self.status_label = tk.Label(frame, text="Ready.", anchor="w", fg="#555")
        self.status_label.pack(fill=tk.X)

        self.output_text = scrolledtext.ScrolledText(frame, width=96, height=24, state="disabled", wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, pady=(12, 0), expand=True)

        tk.Label(frame, text="Detected Suspicious Bot Accounts:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 4))
        self.bots_text = scrolledtext.ScrolledText(frame, width=96, height=8, state="disabled", wrap=tk.NONE)
        self.bots_text.pack(fill=tk.BOTH, pady=(0, 8), expand=False)

    def append_log(self, message: str) -> None:
        self.output_text.configure(state="normal")
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.configure(state="disabled")

    def set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def set_buttons_state(self, enabled: bool) -> None:
        self.run_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def clear_output(self) -> None:
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.configure(state="disabled")
        self.bots_text.configure(state="normal")
        self.bots_text.delete("1.0", tk.END)
        self.bots_text.configure(state="disabled")

    def start_pipeline(self) -> None:
        video_id = self.video_id_var.get().strip()
        if not video_id:
            messagebox.showwarning("Input required", "Please enter a YouTube video ID.")
            return

        try:
            max_comments = int(self.max_comments_var.get().strip())
        except ValueError:
            messagebox.showwarning("Invalid input", "Please enter a valid number of comments.")
            return

        if max_comments < 1 or max_comments > MAX_COMMENTS:
            messagebox.showwarning("Invalid input", f"Number of comments must be between 1 and {MAX_COMMENTS}.")
            return

        self.clear_output()
        self.set_status("Running pipeline...")
        self.set_buttons_state(False)

        thread = threading.Thread(target=self.execute_pipeline, args=(video_id, max_comments), daemon=True)
        thread.start()

    def gui_stage_callback(self, message: str) -> None:
        self.root.after(0, self.append_log, message)
        self.root.after(0, self.set_status, message)

    def show_results(self, result: dict) -> None:
        self.append_log(f"Comments fetched: {result['comments_fetched']}")
        self.append_log(f"Suspicious accounts found: {len(result['suspicious_accounts'])}")
        if result["suspicious_bots"]:
            self.append_log("Detected suspicious bot accounts:")
            for bot in result["suspicious_bots"]:
                comment = bot["example_comment"].replace("\n", " ")
                self.append_log(f"  - {bot['author']}: {comment}")
        else:
            self.append_log("No suspicious bot accounts detected.")

    def execute_pipeline(self, video_id: str, max_comments: int) -> None:
        try:
            result = run_pipeline(video_id, max_comments, stage_callback=self.gui_stage_callback)
            self.root.after(0, self.show_results, result)
            self.root.after(0, self.set_status, f"Finished: {result['comments_fetched']} comments analyzed.")
            self.root.after(0, self.update_bot_list, result["suspicious_bots"])
        except Exception as exc:
            self.root.after(0, self.append_log, f"ERROR: {exc}")
            self.root.after(0, self.set_status, "Pipeline failed.")
            self.root.after(0, messagebox.showerror, "Pipeline Error", f"An error occurred: {exc}")
        finally:
            self.root.after(0, self.set_buttons_state, True)

    def update_bot_list(self, bot_accounts: List[dict]) -> None:
        self.bots_text.configure(state="normal")
        self.bots_text.delete("1.0", tk.END)
        for bot in bot_accounts:
            comment = bot["example_comment"].replace("\n", " ")
            self.bots_text.insert(tk.END, f"{bot['author']}: {comment}\n")
        self.bots_text.configure(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = BotDetectionApp(root)
    root.mainloop()
