"""Consistent readable colors for normal, hovered, and disabled controls."""
from __future__ import annotations

import customtkinter as ctk

ACCENT = "#4866e8"
ACCENT_HOVER = "#3654cc"
INK = "#1e2c46"
MUTED = "#6b7890"
BG = "#f3f6fb"
LIGHT = "#edf1fa"
LIGHT_HOVER = "#dce5f6"
LIGHT_ACTIVE = "#cddaff"
BUTTON_TEXT = "#304aa8"
DISABLED_BG = "#e7ecf4"
DISABLED_TEXT = "#59677f"


def _dark_background(master, color):
    while color == "transparent" and master is not None:
        try:
            color = master.cget("fg_color")
        except (ValueError, AttributeError):
            color = "white"
        master = getattr(master, "master", None)
    if isinstance(color, (tuple, list)):
        color = color[0]
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
        return .2126 * red + .7152 * green + .0722 * blue < 150
    return color not in {"white", "transparent"}


class Button(ctk.CTkButton):
    """Keep the enabled palette when temporarily showing a disabled control."""
    def __init__(self, master, **kwargs):
        foreground = kwargs.get("fg_color", ACCENT)
        dark = _dark_background(master, foreground)
        text = kwargs.get("text_color", "white" if dark else BUTTON_TEXT)
        if not dark and text in {ACCENT, MUTED}:
            text = BUTTON_TEXT
        self._explicit_hover = "hover_color" in kwargs
        self._enabled_palette = {
            "fg_color": foreground,
            "hover_color": kwargs.get("hover_color", ACCENT_HOVER if dark else LIGHT_HOVER),
            "text_color": text,
            "text_color_disabled": DISABLED_TEXT,
        }
        kwargs.update(self._enabled_palette)
        if kwargs.get("state") == "disabled":
            kwargs.update(fg_color=DISABLED_BG, hover_color=DISABLED_BG)
        super().__init__(master, **kwargs)

    def configure(self, require_redraw=False, **kwargs):
        for key in self._enabled_palette:
            if key in kwargs:
                self._enabled_palette[key] = kwargs[key]
        if "hover_color" in kwargs:
            self._explicit_hover = True
        if "fg_color" in kwargs and not self._explicit_hover:
            dark = _dark_background(self.master, kwargs["fg_color"])
            self._enabled_palette["hover_color"] = ACCENT_HOVER if dark else LIGHT_HOVER
        state = kwargs.get("state", self.cget("state"))
        kwargs.update(self._enabled_palette)
        if state == "disabled":
            kwargs.update(fg_color=DISABLED_BG, hover_color=DISABLED_BG)
        super().configure(require_redraw=require_redraw, **kwargs)


class OptionMenu(ctk.CTkOptionMenu):
    def __init__(self, master, **kwargs):
        for key, value in {
            "fg_color": LIGHT, "text_color": INK,
            "button_color": LIGHT_HOVER, "button_hover_color": LIGHT_ACTIVE,
            "dropdown_fg_color": "white", "dropdown_hover_color": LIGHT_HOVER,
            "dropdown_text_color": INK, "text_color_disabled": DISABLED_TEXT,
        }.items():
            kwargs.setdefault(key, value)
        super().__init__(master, **kwargs)


def apply_theme():
    ctk.ThemeManager.theme["CTkFont"].update(family="Microsoft YaHei UI", size=14)
    ctk.ThemeManager.theme["CTkComboBox"].update(
        button_color=LIGHT_HOVER, button_hover_color=LIGHT_ACTIVE,
        dropdown_fg_color="white", dropdown_hover_color=LIGHT_HOVER,
        dropdown_text_color=INK, text_color=INK,
    )
