# Audited ARM extension sources

This is the project's freestanding C/Thumb extension source, native address maps
and linker layouts. It is not the complete Godox source tree. The desktop tool
and CI firmware job apply frozen, original-byte-asserted binary recipes from
`src/regodox/resources/recipes/`; they need no ARM compiler or old lab checkout.

The Canon/Nikon builds preserve live exposure data and CamLCD. S/F/O/L suppress
the stock placeholder exposure values and omit the CamLCD menu tile. Shared GPIO
reads remain stock; key-scanner call sites alone use the modal wrapper.

To change ARM behavior, compile a candidate with the corresponding native/RAM
map, review the diff and protected ranges, run native regression tests, then
regenerate recipe payloads/symbols/fingerprints from the audited input/output.
Simply editing a C file here does not alter a released BIN. Read `AGENTS.md`.
