# Working on reGODOX

Read this file before changing the project. It is a firmware patcher plus a
component emulator, not a complete open-source replacement for Godox firmware.
Keep user-facing desktop text in **English**. Maintain both `README.md` (English)
and `README.ru.md` (Russian) when behavior or setup changes.

## Start here

```sh
uv sync --frozen --all-groups
uv run regodox profiles
uv run regodox build-all --output-dir dist/firmware
uv run --all-groups pytest
uv run --all-groups ruff check src tests tools
```

Use **uv**, the repository `.venv`, `.python-version` and `uv.lock`. Do not use
global pip, copy a developer's venv, or commit caches, executables or `dist/`.
Python 3.12 with Tk is the tested Windows environment. Pillow is the patcher
runtime dependency alongside ttkbootstrap for desktop styling. Unicorn and Capstone are in the `emulator` dependency group;
PyInstaller is in `build`. Keep the patcher independent of emulator libraries.

## Repository map

| Path | Role |
|---|---|
| `src/regodox/engine.py` | Identification, asserted patch application, image encoding, atomic saves |
| `src/regodox/images.py` | EXIF-aware load, 368×448 crop, adaptive four-color quantization |
| `src/regodox/gui.py` | English Tk Firmware Studio: original BIN → all patches + custom splash |
| `src/regodox/theme.py` | Shared ttkbootstrap dark palette; reset styles between Tk interpreters |
| `src/regodox/cli.py` | `inspect`, `patch`, `profiles`, `build-all`; same backend as GUI |
| `src/regodox/resources/profiles.json` | Exact supported versions, sizes, hashes and feature policy |
| `src/regodox/resources/recipes/` | Frozen binary patches with original-byte assertions and symbols |
| `src/regodox/resources/default-splash.*` | Exact default indexed artwork and encoded payload |
| `src/regodox/emulator/` | English UI, core dispatch, modeled camera packets and hardware boundaries |
| `src/regodox/emulator/execution.py` | Shared two-second watchdog for fast Unicorn calls |
| `src/regodox/emulator/cores/` | Audited per-model native address backends; avoid cosmetic refactoring |
| `firmware/original/` | Immutable vendor input BINs; see third-party notice |
| `firmware/src/` | C/Thumb extension sources and address maps for audit, not a full vendor source tree |
| `tests/` | Engine/image/GUI tests and real native ARM/LVGL regression checks |
| `tools/build_windows.py` | Reproducible Windows packaging of both desktop apps |
| `tools/capture_screenshots.py` | Actual application/native UI captures for documentation |
| `.github/workflows/build.yml` | Tests, all firmware outputs and both Windows executables |

The `tools/import_lab.py` and `tools/adapt_gui.py` import tools describe the
one-time migration. Ordinary builds must not need the old lab directory or any
absolute developer path. Never re-run imports against user edits accidentally.

## Non-negotiable firmware rules

1. **Do not flash hardware.** These tools only read/write local files and run
   virtual hardware. Do not add automatic USB/HID/serial writes or updater calls.
2. Never infer compatibility from a filename or size alone. Accept exact known
   original SHA-256 values or normalized fingerprints of this release's patched
   images. Every non-splash byte of a customized build must match its profile.
3. Never overwrite the input BIN. Use a distinct output and verified atomic save.
4. Preserve file length and **all bytes from file offset `0xEF000` onward**.
   This corresponds to main MCU address `0x080F3800`: reserved/storage regions,
   stock journal/service data and the secondary image. The secondary image starts
   at file offset `0xF3800` / main address `0x080F8000`; its own execution base is
   `0x08002000`. Do not confuse these address spaces.
5. Main image base is `0x08004800`. CPU addresses are not file offsets.
6. Keep the shared GPIO reader **stock**. Modal handling belongs only at the
   three physical key-scanner calls. The same GPIO reader serves NOP-timed
   inter-MCU transfers; adding GUI checks to every GPIO read changes timing.
7. Do not call LVGL or allocate in RX/GPIO/IRQ callbacks. Request work for the UI
   timer. Preserve interrupt state and native button/wheel wake behavior.
8. Do not blanket-shift RAM addresses. Nikon and Olympus have individually
   relocated globals. Native cores and recipes contain audited addresses.

## Supported models and feature policy

| ID | Original version | Camera values / CamLCD |
|---|---|---|
| C | X3-C 1.38 | Live aperture/ISO/shutter; default On; menu visible |
| N | X3-N 1.27 | Live aperture/ISO/shutter; default On; menu visible |
| S | X3-S 1.25 | No exposure values; CamLCD Off; menu hidden |
| F | X3-F 1.21 | No exposure values; CamLCD Off; menu hidden |
| O | X3-O 1.09 | No exposure values; CamLCD Off; menu hidden |
| L | X3-L 1.11 | No exposure values; CamLCD Off; menu hidden |

The stock N/S/F/L **main regions are identical**, but secondary firmware differs.
Their files are not interchangeable. O and C also have different main layouts.
Original stock B0 packets are 26 bytes on C and 25 on the other inspected builds.
The emulator's camera values are synthetic packets sent through the native
parser, not a camera simulator or proof of TTL/HSS electrical compatibility.

S/F/O/L write fixed F8 / ISO100 / 1/100 placeholders into the status packet.
Never present them as real camera readings. The manual info panel shows dashes.
CamLCD must remain Off even when loading a saved On record, and absent from the
menu. Do not silently enable it when adding profiles or emulator samples.

There are four stored 100-byte preset payloads and 2–4 visible presets. Hidden
banks retain settings. TEST holds switch after 500 ms; native flash behavior
remains. PRESET overlay is one second. The native/custom persistence code and
bank payload layout must not change without boot, CRC and interruption tests.

The default splash is **368×448, LVGL INDEXED_2BIT**, four arbitrary BGRA8888
palette entries followed by MSB-first packed indices; total **41,232 bytes**.
It occupies the original logo slot, not storage or secondary code. Never add
RGB565 or a new decoder as a side effect of image-editor changes.

## How releases are built

The public tool applies audited, precompiled binary recipes to original BINs.
It does **not** recompile the vendor firmware or run an ARM compiler at runtime.
`regodox build-all` is a complete, reproducible build of the distributed BINs.
Default outputs must equal `default_sha256` in the profiles. Custom artwork may
change only the indexed payload; the patched fingerprint must remain valid.

Changing `firmware/src/*.c` alone does not update a recipe. ARM changes require
a newly compiled and validated candidate, review of every changed range, new
recipe/symbols/fingerprints, and native regression tests. The recipe import tool
requires an explicit audited lab directory; it must never become a runtime
heuristic patcher. Keep original inputs immutable. Do not edit expected hashes
just to make a failed assertion pass.

## Verification required for changes

- Engine: all six originals → exact expected output; input protection; rejection
  of unknown code changes; custom image round-trip; protected tail unchanged;
  patched input recognized independently of filename.
- Images/GUI: crop boundaries, tiny/transparent/rotated images, four-color output,
  live preview, correct model label, default splash and original-file protection.
- Firmware/cores: native boot and splash, TEST/power/wheel/touch, bank count and
  independent settings, STEP M+TTL, menu presence/absence, status parser, save and
  reboot for each affected variant. Check heap stability for modal changes.
- Packaged apps: run `tools/smoke_executables.py` against the actual EXEs. Source
  tests alone do not establish correct DLL/resource packaging.
- Never claim physical device validation from Unicorn tests. Radio, timers,
  GPIO, touch transport and camera packets have modeled boundaries.

Generate screenshots with the screenshot tool or real native framebuffer saves.
Do not replace feature screenshots with drawn mockups. Keep private paths,
virtual flash dumps and crash logs out of documentation and git.

## Scope and publishing

Local builds, tests and reversible edits are routine. Do not push to GitHub,
create releases or publish packages unless the user asks. The configured CI
publishes GitHub Releases on pushed `v*` tags or manual runs with the
`publish_release` checkbox enabled. Manual releases use `build-<run number>` and
target the workflow SHA. Branches, PRs and unchecked manual runs only upload
artifacts. No path automatically flashes a device.
Firmware originals remain third-party material and are not covered by the
project's MIT license. Keep the third-party notice and both language guides.

## Desktop execution and styling

Both apps use ttkbootstrap 1.20.3 with `theme.py`. Keep Pillow ImageFont/ImageDraw
in packaged apps: styled controls need them. Style objects belong to a Tk
interpreter; reset the bootstrap singleton when creating successive test roots.

Default emulator execution avoids Unicorn's costly instruction-count hook. A
shared watchdog stops any call after two seconds. Keep the counted reference
path (`fast=False`) and its framebuffer-equivalence tests. Do not remove the
watchdog for speed. Tk updates only after native display flushes, and its next
timer interval accounts for time already spent executing a frame.

On Windows, Unicorn's handled memory probes confuse pytest's faulthandler;
that plugin is disabled. Real native process failures must still fail CI.
PyInstaller's CFG opt-in also conflicts with Unicorn longjmp. The build clears
only the emulator EXE's CFG opt-in before testing/checksumming; the patcher
retains CFG. Do not change Windows mitigation settings. Read `docs/development.md`.

Do not run concurrent uv commands that select different dependency groups in
the same `.venv`: uv sync can prune dependencies underneath a running test.
Use `--all-groups` for concurrent local host commands. Per-app build environments
remain separate and contain only their own frozen dependency groups.
