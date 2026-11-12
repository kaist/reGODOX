# Development notes

Read [AGENTS.md](../AGENTS.md) first. Python 3.12/Tk on Windows is the reference
desktop environment. Use uv and the committed lockfile.

## Firmware pipeline

Profiles pin six complete original images by SHA-256 and length. Recipes contain
offset/before/after segments, injected symbols and STEP symbols. `engine.build`
verifies identity, asserts original bytes, applies the recipe, inserts the indexed
splash, validates the executable fingerprint and round-trips pixel data.
`save_atomic` refuses source overwrite and verifies a temporary file before replacement.

Main-image load address: `0x08004800`. Bytes from **file offset `0xEF000` onward**
are immutable, including the secondary-controller image. Presets use main flash
pages `0x080F4000` and `0x080F5000`; stock settings journal: `0x080F7800`.

The 368 × 448 splash is LVGL indexed 2-bit: 16 BGRA palette bytes plus 41,216
pixel bytes, total **41,232**. The four colors are arbitrary RGB colors selected
from the image. Current builds do not use RGB565 for the splash. Default indexed
artwork is retained verbatim for golden output hashes.

C/ASM, linker scripts and address maps under `firmware/src/` are audit snapshots.
Editing them alone does not regenerate recipes. Native changes require an ARM
build for the pinned revision, updated recipes/hashes/symbols and regression
tests. Never loosen identity checks to accept a new vendor revision. The import
tools are one-time migration utilities, not normal build steps.

## Emulator

Real firmware functions and LVGL execute in Unicorn. Hardware models cover flash,
touch packets, GPIO keys, encoder input, OLED flushes, radio calls and camera
packets. Physical boot/focus transitions need explicit compatibility shims.

Pillow converts framebuffer RGB565 in native code. Tk updates only after a
firmware flush. Event scheduling subtracts execution time from the next interval.
Per-instruction counting makes repeated short Unicorn calls expensive. The
factory uses uncounted execution with one shared watchdog; each call retains a
two-second wall-time budget. `create_core(..., fast=False)` uses the original
instruction-counted path. Explicit small instruction budgets are preserved.
`tools/benchmark_emulator.py` reports reference/optimized performance and display
conversion time. Tests must not assert speed ratios.

Pytest's faulthandler plugin is disabled: handled Unicorn Windows memory probes
otherwise emit misleading fatal-exception dumps even when tests pass. Actual
Python exceptions and process failures still fail tests.

## Packaging

Each app has an independent frozen uv environment under `build/environments/`.
System/user Python packages are disabled. Dynamic Unicorn architecture modules
must be collected explicitly. ttkbootstrap requires Pillow ImageDraw/ImageFont;
do not exclude them when reducing bundle size.

PyInstaller's CFG-enabled host conflicts with
[Unicorn's Windows longjmp](https://github.com/unicorn-engine/unicorn/issues/2281).
`tools/finalize_emulator.py` clears only this unsigned emulator's PE CFG opt-in,
preserves ASLR/DEP, and updates the checksum before EXE tests/release checksums.
The patcher retains CFG. Windows mitigation settings are not changed. If signing
is added, sign after this step.

`tools/smoke_executables.py` runs actual one-file EXEs: Tk initialization, packaged
artwork, complete patching and all six native cores. Source tests cannot catch
missing dynamically loaded modules or an incompatible host PE.

## Releases and screenshots

Windows CI uses uv throughout. Packaging requires six golden firmware hashes and
successful EXE smoke reports. ZIP timestamps are stable; EXEs are not promised
byte-identical between machines. Tags `v*` publish release assets after checks;
branches/PRs only upload Actions artifacts. CI never flashes hardware.

`tools/capture_screenshots.py` captures real Windows application windows. Feature
frames are native LVGL renders. Keep both READMEs and screenshots current.
