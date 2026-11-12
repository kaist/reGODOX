# Third-party material

The original BINs in `firmware/original/` are Godox X3 application firmware,
retained as exact, hash-pinned inputs for the requested builds and tests. They
remain third-party material; the project MIT license does not grant rights to
the vendor firmware. The resulting modified BINs also contain vendor code.

Official product, firmware and manual references:

- https://godox.com/product-a/X3.html
- https://www.godox.com/static/upload/file/20240830/1724984081444048.pdf

The native emulator executes firmware code, including its LVGL UI. It does not
bundle a separately rebuilt LVGL library. Python, Tcl/Tk, Pillow, Unicorn,
Capstone, PyInstaller and their dependencies retain their own licenses. Their
package/license files accompany installed dependencies and packaged runtimes.

The default reGODOX artwork was created with the built-in image generation tool
and converted to a four-color indexed resource. Its generation prompt is saved
in `docs/artwork-prompt.txt`.
# Desktop styling

ttkbootstrap 1.20.3 is MIT licensed. Its Pillow-generated controls are included
with both desktop applications. See https://github.com/israel-dryer/ttkbootstrap.

