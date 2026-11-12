"""Opt this unsigned emulator EXE out of CFG before release checksums/signing.

Unicorn's Windows longjmp is incompatible with a CFG-enabled host executable:
https://github.com/unicorn-engine/unicorn/issues/2281
Only this executable's PE opt-in bit changes; system settings, ASLR and DEP stay.
"""
from pathlib import Path
import sys
import pefile


def main():
    path=Path(sys.argv[1]);pe=pefile.PE(str(path))
    if pe.OPTIONAL_HEADER.Magic!=0x20b:raise RuntimeError('Expected x64 PE image')
    before=pe.OPTIONAL_HEADER.DllCharacteristics
    pe.OPTIONAL_HEADER.DllCharacteristics=before&~0x4000
    pe.OPTIONAL_HEADER.CheckSum=pe.generate_checksum()
    pe.write(str(path));pe.close()
    verified=pefile.PE(str(path))
    if verified.OPTIONAL_HEADER.DllCharacteristics!=before&~0x4000:
        raise RuntimeError('Emulator CFG compatibility adjustment failed')
    verified.close()
    print('Emulator PE verified: CFG opt-in cleared; ASLR/DEP flags preserved.')


if __name__=='__main__':main()
