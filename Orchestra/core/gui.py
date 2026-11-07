"""
Orchestra of Experts - Desktop GUI

Features:
- Chat window
- Attachment button (files added to the next message context)
- Retractable sidebar with expert folder layout + checkboxes
- Multi-select experts → Judge is automatically enabled
- Model / expert swapping via the sidebar ticks

Requires: customtkinter (auto-installed if missing)
Compatible with: Linux, macOS, Windows
"""

from __future__ import annotations

import sys
import subprocess
import threading
import importlib.util
from pathlib import Path
from tkinter import filedialog, messagebox

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))


def _ensure_customtkinter() -> bool:
    if importlib.util.find_spec("customtkinter") is not None:
        return True
    print("[GUI] customtkinter not found — installing...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "customtkinter"],
            check=True,
        )
        return importlib.util.find_spec("customtkinter") is not None
    except Exception as e:
        print(f"[GUI] Failed to install customtkinter: {e}")
        return False


if not _ensure_customtkinter():
    print("[GUI] Cannot start without customtkinter.")
    sys.exit(1)

import customtkinter as ctk

from config import get_config, update_config, save_config
from router import Conductor
from memory import MemoryPalace


class OrchestraGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.cfg = get_config()
        ctk.set_appearance_mode(self.cfg.get("gui_theme", "dark"))
        ctk.set_default_color_theme("blue")

        self.title("Orchestra of Experts")
        self.geometry(
            f"{self.cfg.get('gui_width', 1100)}x{self.cfg.get('gui_height', 720)}"
        )
        self.minsize(800, 500)

        # Core backend
        orchestra_root = CURRENT_DIR.parent
        self.conductor = Conductor(orchestra_root=orchestra_root)
        self.palace = self.conductor.palace

        # State
        self.enabled_experts: set[str] = set(self.cfg.get("enabled_experts") or [])
        self.attachments: list[Path] = []
        self.sidebar_visible = self.cfg.get("sidebar_visible", True)
        self._busy = False

        # If nothing saved yet, enable all discovered experts
        if not self.enabled_experts:
            self.enabled_experts = set(self.conductor.list_experts())

        self._build_layout()
        self._refresh_sidebar()
        self._append_system("Orchestra GUI ready. Select experts in the sidebar, then chat.")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        self.sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_header.pack(fill="x", padx=8, pady=(10, 4))

        ctk.CTkLabel(
            self.sidebar_header, text="Experts", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        self.btn_toggle_sidebar = ctk.CTkButton(
            self.sidebar_header,
            text="⟨",
            width=32,
            command=self._toggle_sidebar,
        )
        self.btn_toggle_sidebar.pack(side="right")

        self.sidebar_scroll = ctk.CTkScrollableFrame(self.sidebar, label_text="")
        self.sidebar_scroll.pack(fill="both", expand=True, padx=6, pady=6)

        self.expert_vars: dict[str, ctk.BooleanVar] = {}

        # Sidebar footer
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(fill="x", padx=8, pady=8)

        ctk.CTkButton(footer, text="Select all", width=100, command=self._select_all).pack(
            side="left", padx=(0, 4)
        )
        ctk.CTkButton(footer, text="Clear", width=80, command=self._clear_all).pack(side="left")

        # Floating re-open button (when sidebar hidden)
        self.btn_show_sidebar = ctk.CTkButton(
            self, text="⟩ Experts", width=90, command=self._toggle_sidebar
        )
        # placed later when hidden

        # --- Main chat area ---
        main = ctk.CTkFrame(self, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.chat_box = ctk.CTkTextbox(main, wrap="word", state="disabled")
        self.chat_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 4))

        # Attachment strip
        self.attach_frame = ctk.CTkFrame(main, fg_color="transparent")
        self.attach_frame.grid(row=1, column=0, sticky="ew", padx=10)
        self.attach_label = ctk.CTkLabel(self.attach_frame, text="", anchor="w")
        self.attach_label.pack(fill="x")

        # Input row
        input_row = ctk.CTkFrame(main, fg_color="transparent")
        input_row.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        input_row.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkEntry(
            input_row, placeholder_text="Message the Orchestra…", height=40
        )
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.input_box.bind("<Return>", lambda e: self._on_send())

        self.btn_attach = ctk.CTkButton(
            input_row, text="📎", width=40, command=self._on_attach
        )
        self.btn_attach.grid(row=0, column=1, padx=(0, 6))

        self.btn_send = ctk.CTkButton(
            input_row, text="Send", width=80, command=self._on_send
        )
        self.btn_send.grid(row=0, column=2)

        # Status bar
        self.status_var = ctk.StringVar(value="Ready")
        self.status_bar = ctk.CTkLabel(main, textvariable=self.status_var, anchor="w")
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

        if not self.sidebar_visible:
            self.sidebar.grid_remove()
            self.btn_show_sidebar.place(x=8, y=12)

    # ------------------------------------------------------------------
    # Sidebar experts
    # ------------------------------------------------------------------
    def _refresh_sidebar(self):
        for child in self.sidebar_scroll.winfo_children():
            child.destroy()
        self.expert_vars.clear()

        experts = self.conductor.list_experts()
        if not experts:
            ctk.CTkLabel(self.sidebar_scroll, text="No experts found").pack(anchor="w")
            return

        # Group by top-level category for readability
        groups: dict[str, list[str]] = {}
        for key in experts:
            top = key.split("/")[0]
            groups.setdefault(top, []).append(key)

        for group_name in sorted(groups.keys()):
            ctk.CTkLabel(
                self.sidebar_scroll,
                text=group_name,
                font=ctk.CTkFont(weight="bold"),
            ).pack(anchor="w", pady=(8, 2))

            for key in sorted(groups[group_name]):
                var = ctk.BooleanVar(value=key in self.enabled_experts)
                self.expert_vars[key] = var

                cb = ctk.CTkCheckBox(
                    self.sidebar_scroll,
                    text=key,
                    variable=var,
                    command=self._on_expert_toggle,
                )
                cb.pack(anchor="w", padx=(12, 0), pady=2)

        self._update_judge_hint()

    def _on_expert_toggle(self):
        self.enabled_experts = {
            k for k, v in self.expert_vars.items() if v.get()
        }

        # Auto-enable Judge when multiple experts selected
        if self.cfg.get("auto_judge_when_multiple", True):
            judge_key = self.cfg.get("judge_expert_key", "Judge")
            selected = [k for k in self.enabled_experts if k != judge_key]
            if len(selected) >= 2 and judge_key in self.expert_vars:
                if judge_key not in self.enabled_experts:
                    self.expert_vars[judge_key].set(True)
                    self.enabled_experts.add(judge_key)
                    self._append_system(
                        f"Multiple experts selected → '{judge_key}' automatically enabled."
                    )

        update_config(enabled_experts=sorted(self.enabled_experts))
        self._update_judge_hint()

    def _update_judge_hint(self):
        judge_key = self.cfg.get("judge_expert_key", "Judge")
        selected = [k for k in self.enabled_experts if k != judge_key]
        if len(selected) >= 2:
            self.status_var.set(
                f"{len(selected)} experts + Judge — multi-expert mode"
            )
        else:
            self.status_var.set(
                f"{len(self.enabled_experts)} expert(s) enabled"
            )

    def _select_all(self):
        for var in self.expert_vars.values():
            var.set(True)
        self._on_expert_toggle()

    def _clear_all(self):
        for var in self.expert_vars.values():
            var.set(False)
        self._on_expert_toggle()

    def _toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible:
            self.btn_show_sidebar.place_forget()
            self.sidebar.grid(row=0, column=0, sticky="nsw")
            self.btn_toggle_sidebar.configure(text="⟨")
        else:
            self.sidebar.grid_remove()
            self.btn_show_sidebar.place(x=8, y=12)
        update_config(sidebar_visible=self.sidebar_visible)

    # ------------------------------------------------------------------
    # Chat helpers
    # ------------------------------------------------------------------
    def _append_chat(self, role: str, text: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{role}:\n{text}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _append_system(self, text: str):
        self._append_chat("System", text)

    def _on_attach(self):
        paths = filedialog.askopenfilenames(
            title="Attach files",
            filetypes=[
                ("Text / code", "*.txt *.md *.py *.js *.ts *.php *.json *.yaml *.yml *.csv"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        for p in paths:
            path = Path(p)
            if path not in self.attachments:
                self.attachments.append(path)
        self._refresh_attach_label()

    def _refresh_attach_label(self):
        if not self.attachments:
            self.attach_label.configure(text="")
            return
        names = ", ".join(p.name for p in self.attachments)
        self.attach_label.configure(text=f"Attachments: {names}  (sent with next message)")

    def _build_message_with_attachments(self, text: str) -> str:
        if not self.attachments:
            return text

        parts = [text, "", "--- Attached files ---"]
        for path in self.attachments:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                # Cap size so we don't blow the context
                if len(content) > 12000:
                    content = content[:12000] + "\n…[truncated]"
                parts.append(f"\n### File: {path.name}\n```\n{content}\n```")
            except Exception as e:
                parts.append(f"\n### File: {path.name}\n[Could not read: {e}]")

        self.attachments.clear()
        self._refresh_attach_label()
        return "\n".join(parts)

    def _on_send(self):
        if self._busy:
            return

        text = self.input_box.get().strip()
        if not text and not self.attachments:
            return

        self.input_box.delete(0, "end")
        message = self._build_message_with_attachments(text or "(see attachments)")

        self._append_chat("You", text or "(attachments only)")
        self._busy = True
        self.btn_send.configure(state="disabled")
        self.status_var.set("Thinking…")

        # Run inference off the UI thread
        thread = threading.Thread(target=self._run_inference, args=(message,), daemon=True)
        thread.start()

    def _run_inference(self, message: str):
        try:
            # Restrict routing to enabled experts by temporarily filtering
            # (simple approach: if only one non-judge expert, force it)
            enabled = list(self.enabled_experts)
            judge_key = self.cfg.get("judge_expert_key", "Judge")
            non_judge = [e for e in enabled if e != judge_key]

            if len(non_judge) == 1:
                # Force single expert path
                expert_key = non_judge[0]
                if expert_key in self.conductor.available_experts:
                    path = self.conductor.available_experts[expert_key]["path"]
                    memory_block = self.palace.recall_for_prompt(
                        message, limit=self.cfg.get("memory_recall_limit", 3)
                    )
                    instruction = message
                    if memory_block:
                        instruction = f"{memory_block}\n\n---\n\nCurrent user request:\n{message}"

                    ok = self.conductor.loader.load(path)
                    if not ok:
                        result = f"Failed to load expert: {expert_key}"
                    else:
                        result = self.conductor.loader.run(
                            instruction,
                            max_tokens=self.cfg.get("max_tokens", 1024),
                            temperature=self.cfg.get("temperature", 0.7),
                        )
                else:
                    result = self.conductor.run(
                        message,
                        auto_remember=self.cfg.get("auto_remember", False),
                    )
            else:
                # Multiple (or none) — use normal Conductor routing
                # TODO: true multi-expert + Judge pipeline
                result = self.conductor.run(
                    message,
                    auto_remember=self.cfg.get("auto_remember", False),
                )
                if len(non_judge) >= 2:
                    result = (
                        f"[Multi-expert mode: {', '.join(non_judge)}]\n"
                        f"(Full parallel+Judge pipeline coming next)\n\n"
                        f"{result}"
                    )

        except Exception as e:
            result = f"Error: {e}"

        self.after(0, lambda: self._on_inference_done(result))

    def _on_inference_done(self, result: str):
        self._append_chat("Orchestra", result)
        self._busy = False
        self.btn_send.configure(state="normal")
        self._update_judge_hint()


def main():
    app = OrchestraGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
