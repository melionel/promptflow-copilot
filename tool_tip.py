import tkinter as tk

class ToolTip:
    def __init__(self, widget, normal_text, disabled_text=None):
        self.widget = widget
        self.normal_text = normal_text
        self.disabled_text = disabled_text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        if self.disabled_text and self.widget.cget('state') == tk.DISABLED:
            current_text = self.disabled_text
        else:
            current_text = self.normal_text

        label = tk.Label(self.tooltip, text=current_text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
