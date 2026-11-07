"""One multimodal API settings dialog for all AI entry points."""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from .. import service
from ..settings import AIConfig, AI_REQUIRED
from .dialogs import ACCENT, Button, OptionMenu, INK, MUTED, Modal, label


class AISettingsDialog(Modal):
    def __init__(self, master):
        super().__init__(master, "AI 接口设置", 780, 620)
        try:
            self.original = service.ai_settings()
        except ValueError:
            self.original = AIConfig()
        label(self, "连接你的多模态 AI", 24).pack(anchor="w", padx=28, pady=(26, 7))
        label(self, AI_REQUIRED + " 识图和通知调课共用这一份配置.", 13, MUTED, wraplength=710, justify="left").pack(anchor="w", padx=28, pady=(0, 15))
        panel = ctk.CTkFrame(self, fg_color="white", corner_radius=14)
        panel.pack(fill="x", padx=28)
        panel.grid_columnconfigure(1, weight=1)
        label(panel, "接入方式").grid(row=0, column=0, padx=20, pady=14, sticky="w")
        mode = OptionMenu(panel, values=["自定义兼容接口", "本地 Ollama"], command=self.preset, fg_color="#edf1fa", text_color=INK)
        mode.grid(row=0, column=1, padx=20, pady=14, sticky="ew")
        self.fields = {}
        for row, (key, title, placeholder) in enumerate([
            ("base_url", "API 地址", "https://你的服务地址/v1"),
            ("model", "模型名称", "填写支持文字和图片输入的模型名称"),
            ("api_key", "API Key", "本地 Ollama 可留空"),
            ("timeout", "超时秒数", "90"),
        ], 1):
            label(panel, title).grid(row=row, column=0, padx=20, pady=10, sticky="w")
            entry = ctk.CTkEntry(panel, height=36, placeholder_text=placeholder, show="*" if key == "api_key" else "")
            value = getattr(self.original, key)
            if value:
                entry.insert(0, str(value))
            entry.grid(row=row, column=1, padx=20, pady=10, sticky="ew")
            self.fields[key] = entry
        self.status = label(self, "保存后可用自检验证图片识别能力.", 13, MUTED, wraplength=710, justify="left")
        self.status.pack(anchor="w", padx=28, pady=18)
        label(self, "API Key 只保存在本机; Windows 使用当前用户加密. 自检会发送一张程序生成的数字图片.", 12, MUTED, wraplength=710, justify="left").pack(anchor="w", padx=28)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=28, pady=22)
        Button(footer, text="关闭", width=90, fg_color="#dfe5f0", text_color=INK, command=self.close).pack(side="left")
        Button(footer, text="保存配置", width=115, fg_color="#dfe5f0", text_color=INK, command=self.save).pack(side="right", padx=(10, 0))
        self.test_button = Button(footer, text="保存并自检", fg_color=ACCENT, command=lambda: self.save(True))
        self.test_button.pack(side="right")

    def preset(self, name):
        if name == "本地 Ollama":
            self.fields["base_url"].delete(0, "end")
            self.fields["base_url"].insert(0, "http://localhost:11434/v1")

    def save(self, test=False):
        try:
            values = {key: field.get().strip() for key, field in self.fields.items()}
            values["timeout"] = int(values["timeout"])
            config = AIConfig(**values)
            if config.signature == self.original.signature:
                config.verified_signature = self.original.verified_signature
            service.save_ai_settings(config)
            self.original = config
            self.status.configure(text="配置已保存. 多模态能力" + ("已验证." if config.vision_verified else "尚待自检."))
            if test:
                self.test_button.configure(state="disabled")
                self.app.run_task(lambda: service.test_ai(config), self.tested, "正在验证图片识别能力...", self.failed)
        except (ValueError, OSError) as exc:
            messagebox.showerror("请核对接口设置", str(exc), parent=self)

    def tested(self, text):
        if self.winfo_exists():
            self.status.configure(text=text, text_color="#18835b")
            self.test_button.configure(state="normal")

    def failed(self, exc):
        if self.winfo_exists():
            self.status.configure(text=str(exc), text_color="#b44444")
            self.test_button.configure(state="normal")
