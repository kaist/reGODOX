"""One-time migration of the original crop editor into the project package."""
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
text=(Path(sys.argv[1])/'splash-tool/app.py').read_text(encoding='utf-8')
text=text.replace('from core import (HEIGHT, WIDTH, crop_image,\n                  indexed_image, load_image, patch_firmware, validate_firmware)',
    'from .engine import WIDTH, HEIGHT, build, identify, default_splash, resource, save_atomic\n'
    'from .images import crop_image, indexed_image, load_image')
text=text.replace('class SplashEditor:', 'class FirmwareStudio:')
text=text.replace('Splash Studio | Godox X3-C','reGODOX | Firmware Studio')
text=text.replace('icon_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets/splash.ico"',
                  'icon_path = resource("regodox.ico")')
text=text.replace('self.image = None','self.is_default = True\n        self.profile = None\n        self.image = None',1)
text=text.replace('text="Splash Studio"','text="reGODOX"')
text=text.replace('GODOX X3-C  /  368 × 448','FIRMWARE STUDIO  /  GODОX X3')
text=text.replace('GODОX','GODOX')
text=text.replace('Your image. Four colors. A splash that feels like yours.','Presets. Better controls. Your own splash.')
text=text.replace('text="Choose image…", command=self.choose_image).pack(side="left")',
    'text="Choose image…", command=self.choose_image).pack(side="left")\n'
    '        ttk.Button(actions, text="Default splash", command=self.use_default).pack(side="left", padx=8)')
text=text.replace('03  Choose your patched firmware','03  Select firmware — all patches are included')
text=text.replace('V9 CamLCD BIN  ·  verified before patching','C 1.38 · N 1.27 · S 1.25 · F 1.21 · O 1.09 · L 1.11')
text=text.replace('Save custom firmware…','Build firmware…')
text=text.replace('title="Choose patched V9 CamLCD firmware"','title="Choose original Godox X3 firmware"')
text=text.replace('validate_firmware(data)','self.profile, kind = identify(data)')
text=text.replace('self.firmware_label.configure(text=Path(path).name, foreground=ACCENT)',
    'self.firmware_label.configure(text=self.profile.label + "  |  " + kind, foreground=ACCENT)')
text=text.replace('self.status.set("Firmware verified. All bytes outside the splash will be preserved.")',
    'self.status.set("Verified " + self.profile.label + ". All reGODOX patches will be applied; "\n'
    '                                + ("CamLCD available." if self.profile.camlcd_menu else "CamLCD disabled; menu hidden."))')
text=text.replace('self.image = image\n                self.image_label',
                  'self.image = image\n                self.is_default = False\n                self.image_label')
text=text.replace('        if len(sys.argv) > 1:\n            root.after(100, lambda: self.open_path(sys.argv[1]))',
                  '        self.use_default()')
text=text.replace('    def choose_image(self):',
    '    def use_default(self):\n'
    '        self.is_default = True\n'
    '        self.image = default_splash().convert("RGB")\n'
    '        self.image_label.configure(text="Default reGODOX splash")\n'
    '        self.reset_crop()\n\n'
    '    def choose_image(self):')
text=text.replace('self.preview = indexed_image(crop, self.dither.get())',
    'self.preview = (default_splash() if self.is_default and self.zoom.get() == 1 and not self.dither.get()\n'
    '                        else indexed_image(crop, self.dither.get()))')
start=text.index('    def save(self):');end=text.index('    def enable_drop(self):',start)
text=text[:start]+'''    def save_to(self, destination):
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
            messagebox.showinfo("Firmware built", self.profile.label + "\\n\\n" + str(path)
                + "\\n\\nAll patches and the splash were verified. Use the matching model only.", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Build failed", str(exc), parent=self.root)

'''+text[end:]
start=text.index('def main():')
text=text[:start]+'''def main():
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
        args.smoke_test.write_text(json.dumps(report, indent=2), encoding="utf-8")
        root.tk.call(root.protocol("WM_DELETE_WINDOW"))
        return
    if args.file:
        root.after(100, lambda: app.open_path(args.file))
    root.mainloop()


if __name__ == "__main__":
    main()
'''
(root/'src/regodox/gui.py').write_text(text,encoding='utf-8')
print('GUI migrated.')
