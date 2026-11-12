"""Exercise actual frozen GUIs and their bundled resources/DLLs."""
from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def run(args):
    startup=None
    if sys.platform=='win32':
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow=0
    env=os.environ.copy()
    for name in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):env.pop(name,None)
    subprocess.run([str(a) for a in args],cwd=ROOT,env=env,startupinfo=startup,check=True,timeout=180)


def main():
    with tempfile.TemporaryDirectory(prefix='regodox-exe-smoke-') as directory:
        d=Path(directory);p=d/'patcher.json';e=d/'emulator.json'
        run([ROOT/'dist/windows/reGODOX-Firmware-Studio.exe','--smoke-test',p,
             '--firmware',ROOT/'firmware/original/X3_C_v1.38_app.bin','--output',d/'custom.bin'])
        patcher=json.loads(p.read_text());assert patcher['all_patches_applied'] and patcher['GUI_created']
        run([ROOT/'dist/windows/reGODOX-Emulator.exe','--smoke-test',e])
        emulator=json.loads(e.read_text());assert emulator['ok'] and set(emulator['models'])==set('CNSFOL')
        checksums={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (ROOT/'dist/windows').glob('*.exe')}
        (ROOT/'dist/windows/executable-smoke.json').write_text(json.dumps(
            {'patcher':patcher,'emulator':emulator,'executables':checksums},indent=2))
        print('PASS both Windows EXEs: GUI/resources, real patching and all six native emulator cores.')


if __name__=='__main__':main()
