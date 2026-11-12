"""Small, dependency-light Windows splash editor. All UI text is English."""
from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .engine import WIDTH, HEIGHT, build, identify, default_splash, resource, save_atomic
from .images import crop_image, indexed_image, load_image
from . import theme

BG, CARD, BORDER = theme.BG, theme.CARD, "#303c4c"
TEXT, MUTED, ACCENT = "#edf1f7", "#9aa8bc", "#7cddba"


class FirmwareStudio:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("reGODOX | Firmware Studio")
        icon_path = resource("regodox.ico")
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
        root.configure(bg=BG)
        root.geometry("1010x" + str(min(860, root.winfo_screenheight() - 70)))
        self.view_h = max(200, min(365, root.winfo_screenheight() - 635))
        self.view_w = round(self.view_h * WIDTH / HEIGHT)
        self.is_default = True
        self.profile = None
        self.image = None
        self.preview = None
        self.firmware = None
        self.firmware_path = None
        self.center = (0.0, 0.0)
        self.pending = None
        self.drag = None
        self.zoom = tk.DoubleVar(value=1)
        self.dither = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Start by dropping an image or choosing a file.")
        self.style = theme.setup(root)

        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        head = ttk.Frame(outer)
        head.pack(fill="x")
        ttk.Label(head, text="reGODOX", font=("Segoe UI",28,"bold")).pack(side="left")
        ttk.Label(head, text="FIRMWARE STUDIO  /  GODOX X3", foreground=ACCENT).pack(side="right", pady=12)
        ttk.Label(outer, text="Presets. Better controls. Your own splash.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 20))
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 15))
        ttk.Button(actions, text="Choose image…", bootstyle="secondary-outline", command=self.choose_image).pack(side="left")
        ttk.Button(actions, text="Default splash", bootstyle="secondary-outline", command=self.use_default).pack(side="left", padx=8)
        self.image_label = ttk.Label(actions, text="PNG, JPG, WebP, BMP or GIF  ·  drag & drop supported",
                                     style="Muted.TLabel")
        self.image_label.pack(side="left", padx=16)

        columns = ttk.Frame(outer)
        columns.pack(fill="x")
        columns.columnconfigure((0, 1), weight=1, uniform="panels")
        for col, (title, subtitle) in enumerate([
            ("01  Frame your image", "Drag to move  ·  scroll to zoom"),
            ("02  Firmware preview", "Exact indexed output  ·  automatic 4-color palette")]):
            box = ttk.Frame(columns)
            box.grid(row=0, column=col, sticky="nsew", padx=(0, 20) if col == 0 else (0, 0))
            ttk.Label(box, text=title, font=("Segoe UI",11,"bold")).pack(anchor="w")
            ttk.Label(box, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(3, 10))
            canvas = tk.Canvas(box, width=self.view_w, height=self.view_h, bg=CARD,
                               highlightthickness=1, highlightbackground=BORDER)
            canvas.pack()
            canvas.create_text(self.view_w / 2, self.view_h / 2,
                               text="Drop your image here" if col == 0 else "Your splash will appear here",
                               width=self.view_w - 20, justify="center",
                               fill=MUTED, font=("Segoe UI", 11), tags="placeholder")
            if col == 0:
                self.source_canvas = canvas
            else:
                self.output_canvas = canvas
        self.source_canvas.bind("<ButtonPress-1>", self.start_drag)
        self.source_canvas.bind("<B1-Motion>", self.move_drag)
        self.source_canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        self.source_canvas.bind("<MouseWheel>", self.scroll)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(15, 4))
        ttk.Label(controls, text="Zoom", style="Muted.TLabel").pack(side="left")
        ttk.Scale(controls, from_=1, to=5, variable=self.zoom, command=lambda _: self.schedule()).pack(
            side="left", fill="x", expand=True, padx=12)
        ttk.Button(controls, text="Reset crop", bootstyle="secondary-outline", command=self.reset_crop).pack(side="left", padx=(0, 20))
        ttk.Checkbutton(controls, text="Dither", bootstyle="success-round-toggle", variable=self.dither,
                        command=self.schedule).pack(side="left")
        self.palette_canvas = tk.Canvas(outer, height=30, bg=BG, highlightthickness=0)
        self.palette_canvas.pack(fill="x", pady=(8, 12))

        ttk.Separator(outer).pack(fill="x", pady=(0, 15))
        footer = ttk.Frame(outer)
        footer.pack(fill="x")
        ttk.Label(footer, text="03  Select firmware — all patches are included", font=("Segoe UI",11,"bold")).pack(anchor="w")
        row = ttk.Frame(footer)
        row.pack(fill="x", pady=(9, 8))
        ttk.Button(row, text="Choose firmware…", bootstyle="info-outline", command=self.choose_firmware).pack(side="left")
        self.firmware_label = ttk.Label(row, text="C 1.38 · N 1.27 · S 1.25 · F 1.21 · O 1.09 · L 1.11",
                                        style="Muted.TLabel")
        self.firmware_label.pack(side="left", padx=16)
        bottom = ttk.Frame(footer)
        bottom.pack(fill="x", pady=(4, 0))
        ttk.Button(bottom, text="Export preview…", bootstyle="secondary-outline", command=self.export_preview).pack(side="left")
        self.save_button = ttk.Button(bottom, text="Build firmware…", bootstyle="success",
                                      command=self.save, state="disabled")
        self.save_button.pack(side="right")
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=910).pack(
            anchor="w", pady=(14, 0))
        root.update_idletasks()
        root.minsize(930, max(600, root.winfo_reqheight()))
        self.enable_drop()
        self.use_default()

    def use_default(self):
        self.is_default = True
        self.image = default_splash().convert("RGB")
        self.image_label.configure(text="Default reGODOX splash")
        self.reset_crop()

    def choose_image(self):
        path = filedialog.askopenfilename(title="Choose splash image", filetypes=[
            ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"), ("All files", "*.*")])
        if path:
            self.open_path(path)

    def choose_firmware(self):
        path = filedialog.askopenfilename(title="Choose original Godox X3 firmware",
                                          filetypes=[("Firmware", "*.bin")])
        if path:
            self.open_path(path)

    def open_path(self, path):
        try:
            if Path(path).suffix.lower() == ".bin":
                data = Path(path).read_bytes()
                self.profile, kind = identify(data)
                self.firmware, self.firmware_path = data, Path(path)
                self.firmware_label.configure(text=self.profile.label + "  |  " + kind, foreground=ACCENT)
                self.status.set("Verified " + self.profile.label + ". All reGODOX patches will be applied; "
                                + ("CamLCD available." if self.profile.camlcd_menu else "CamLCD disabled; menu hidden."))
            else:
                image = load_image(path)
                self.image = image
                self.is_default = False
                self.image_label.configure(text=Path(path).name)
                self.reset_crop()
                self.status.set("Drag the left image to frame it. The right panel is the actual firmware output.")
            self.update_save()
        except Exception as exc:
            messagebox.showerror("Cannot open file", str(exc), parent=self.root)

    def update_save(self):
        self.save_button.configure(state="normal" if self.preview is not None and self.firmware is not None else "disabled")

    def reset_crop(self):
        self.zoom.set(1)
        if self.image:
            self.center = (self.image.width / 2, self.image.height / 2)
            self.render()

    def clamped_center(self):
        if not self.image:
            return
        scale = max(WIDTH / self.image.width, HEIGHT / self.image.height) * self.zoom.get()
        cw, ch = WIDTH / scale, HEIGHT / scale
        self.center = (min(max(self.center[0], cw / 2), self.image.width - cw / 2),
                       min(max(self.center[1], ch / 2), self.image.height - ch / 2))

    def start_drag(self, event):
        self.drag = (event.x, event.y)
        self.source_canvas.configure(cursor="fleur")

    def move_drag(self, event):
        if not self.image or self.drag is None:
            return
        scale = max(self.view_w / self.image.width, self.view_h / self.image.height) * self.zoom.get()
        dx, dy = event.x - self.drag[0], event.y - self.drag[1]
        self.center = (self.center[0] - dx / scale, self.center[1] - dy / scale)
        self.clamped_center()
        self.drag = (event.x, event.y)
        self.schedule()

    def scroll(self, event):
        self.zoom.set(min(5, max(1, self.zoom.get() * (1.12 if event.delta > 0 else 1 / 1.12))))
        self.schedule()

    def schedule(self):
        if self.pending:
            self.root.after_cancel(self.pending)
        self.pending = self.root.after(65, self.render)

    def render(self):
        self.pending = None
        if self.image is None:
            return
        self.clamped_center()
        crop = crop_image(self.image, self.center, self.zoom.get())
        self.preview = (default_splash() if self.is_default and self.zoom.get() == 1 and not self.dither.get()
                        else indexed_image(crop, self.dither.get()))
        size = (self.view_w, self.view_h)
        self.source_tk = ImageTk.PhotoImage(crop.resize(size, Image.Resampling.LANCZOS))
        self.preview_tk = ImageTk.PhotoImage(self.preview.convert("RGB").resize(size, Image.Resampling.NEAREST))
        for canvas, image in [(self.source_canvas, self.source_tk), (self.output_canvas, self.preview_tk)]:
            canvas.delete("all")
            canvas.create_image(0, 0, image=image, anchor="nw")
        p = self.preview.getpalette()
        self.palette_canvas.delete("all")
        for i in range(4):
            r, g, b = p[3 * i:3 * i + 3]
            color = "#{:02X}{:02X}{:02X}".format(r, g, b)
            x = i * 170
            self.palette_canvas.create_rectangle(x, 2, x + 26, 28, fill=color, outline=BORDER)
            self.palette_canvas.create_text(x + 36, 15, anchor="w", text=color, fill=MUTED,
                                             font=("Consolas", 10))
        self.update_save()

    def export_preview(self):
        self.render()
        if self.preview is None:
            return
        path = filedialog.asksaveasfilename(title="Export indexed preview", defaultextension=".png",
                                            initialfile="splash-preview.png", filetypes=[("PNG", "*.png")])
        if path:
            try:
                self.preview.save(path)
            except Exception as exc:
                messagebox.showerror("Export failed", str(exc), parent=self.root)

    def save_to(self, destination):
        self.render()
        if self.firmware is None or self.preview is None:
            raise ValueError("Choose a firmware file first.")
        result, report = build(self.firmware, self.preview)
        save_atomic(Path(destination), result, self.firmware_path)
        self.status.set("Built " + Path(destination).name + "  ·  all patches verified  ·  input unchanged")
        return report

    def save(self):
        if self.firmware is None or self.profile is None:
            return
        path = filedialog.asksaveasfilename(title="Build reGODOX firmware", defaultextension=".bin",
            initialfile=self.profile.output_name, filetypes=[("Firmware", "*.bin")])
        if not path:
            return
        try:
            self.save_to(path)
            messagebox.showinfo("Firmware built", self.profile.label + "\n\n" + str(path)
                + "\n\nAll patches and the splash were verified. Use the matching model only.", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Build failed", str(exc), parent=self.root)

    def enable_drop(self):
        """Use Windows file drops directly, without a bundled drag-and-drop library."""
        if sys.platform != "win32":
            return
        from ctypes import wintypes
        self.root.update_idletasks()
        user = ctypes.WinDLL("user32", use_last_error=True)
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        intptr = ctypes.c_ssize_t
        callback_type = ctypes.WINFUNCTYPE(intptr, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        hwnd = user.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        setter = user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.SetWindowLongW
        setter.argtypes = [wintypes.HWND, ctypes.c_int, intptr]
        setter.restype = intptr
        user.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user.CallWindowProcW.restype = intptr
        shell.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell.DragQueryFileW.restype = wintypes.UINT
        shell.DragFinish.argtypes = [wintypes.HANDLE]

        def procedure(window, message, wp, lp):
            if message == 0x233:  # WM_DROPFILES
                paths = []
                try:
                    for i in range(shell.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)):
                        size = shell.DragQueryFileW(wp, i, None, 0)
                        buffer = ctypes.create_unicode_buffer(size + 1)
                        shell.DragQueryFileW(wp, i, buffer, size + 1)
                        paths.append(buffer.value)
                finally:
                    shell.DragFinish(wp)
                for path in paths:
                    self.root.after_idle(self.open_path, path)
                return 0
            return user.CallWindowProcW(self.old_proc, window, message, wp, lp)

        self.drop_callback = callback_type(procedure)
        ctypes.set_last_error(0)
        self.old_proc = setter(hwnd, -4, ctypes.cast(self.drop_callback, ctypes.c_void_p).value)
        if not self.old_proc and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        shell.DragAcceptFiles(hwnd, True)
        self.drop_hwnd = hwnd

        def close():
            shell.DragAcceptFiles(hwnd, False)
            setter(hwnd, -4, self.old_proc)
            self.root.destroy()
        self.root.protocol("WM_DELETE_WINDOW", close)


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description="reGODOX Firmware Studio")
    parser.add_argument("file", nargs="?")
    parser.add_argument("--smoke-test", type=Path)
    parser.add_argument("--firmware", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    if args.smoke_test:
        root.withdraw()
    app = FirmwareStudio(root)
    if args.smoke_test:
        if not args.firmware or not args.output:
            parser.error("smoke test requires --firmware and --output")
        app.open_path(args.firmware)
        root.update()
        report = app.save_to(args.output)
        report["GUI_created"] = True
        report["drag_drop_callback"] = hasattr(app, "drop_callback")
        args.smoke_test.parent.mkdir(exist_ok=True, parents=True)
        args.smoke_test.write_text(json.dumps(report, indent=2), encoding="utf-8")
        root.tk.call(root.protocol("WM_DELETE_WINDOW"))
        return
    if args.file:
        root.after(100, lambda: app.open_path(args.file))
    root.mainloop()


if __name__ == "__main__":
    main()
