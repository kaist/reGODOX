"""Build each Windows app with uv in its own frozen, isolated environment."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def run(args,env):
    subprocess.run([str(a) for a in args],cwd=ROOT,env=env,check=True)


def build(app):
    uv=shutil.which('uv')
    if not uv:raise RuntimeError('Install uv before building.')
    venv=ROOT/'build/environments'/app
    env=os.environ.copy()
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','CONDA_PREFIX','CONDA_DEFAULT_ENV'):
        env.pop(key,None)
    env.update(UV_PROJECT_ENVIRONMENT=str(venv),UV_LINK_MODE='copy',PYTHONNOUSERSITE='1')
    base=Path(sys._base_executable)
    system=Path(os.environ['SystemRoot'])
    env['PATH']=os.pathsep.join(map(str,[venv/'Scripts',base.parent,system/'System32',system]))
    groups=['--group','build']+(['--group','emulator'] if app=='emulator' else [])
    common=['--project',ROOT,'--frozen','--no-default-groups','--python',base,*groups]
    run([uv,'sync',*common],env)
    cfg=(venv/'pyvenv.cfg').read_text().lower()
    if 'include-system-site-packages = false' not in cfg:
        raise RuntimeError('Build environment exposes system site-packages.')
    python=venv/'Scripts/python.exe'
    packages=json.loads(subprocess.check_output([str(uv),'pip','list','--python',str(python),'--format','json'],
                                               cwd=ROOT,env=env,text=True))
    names={p['name'].lower() for p in packages}
    if app=='patcher' and names&{'unicorn','capstone','numpy','matplotlib'}:
        raise RuntimeError('Unexpected heavy runtime in patcher environment.')
    name='reGODOX-Firmware-Studio' if app=='patcher' else 'reGODOX-Emulator'
    res=ROOT/'src/regodox/resources'
    options=['--noconfirm','--clean','--onefile','--windowed','--noupx','--optimize','2',
        '--name',name,'--icon',str(res/'regodox.ico'),
        '--paths',str(ROOT/'src'),'--add-data',str(res)+os.pathsep+'regodox/resources',
        '--distpath',str(ROOT/'dist/windows'),'--workpath',str(ROOT/'build/pyinstaller'/app),
        '--specpath',str(ROOT/'build/specs')]
    options+=['--collect-data','ttkbootstrap']
    excludes=['numpy','matplotlib','pytest','unittest','PIL.ImageQt','PIL.ImageShow',
              'PIL.ImageCms','PIL._imagingcms','PIL.AvifImagePlugin','PIL._avif']
    if app=='patcher':excludes+=['unicorn','capstone','regodox.emulator']
    else:
        options+=['--add-data',str(ROOT/'firmware/original')+os.pathsep+'originals',
                  '--collect-binaries','unicorn','--collect-submodules','unicorn',
                  '--collect-binaries','capstone']
    for item in excludes:options+=['--exclude-module',item]
    # -I removes user site and Python path environment influence. Explicit --paths
    # is the only project import path passed to PyInstaller.
    run([uv,'run',*common,'python','-I','-m','PyInstaller',*options,ROOT/f'tools/launch_{app}.py'],env)
    if app=='emulator':
        run([uv,'run',*common,'python','-I',ROOT/'tools/finalize_emulator.py',
             ROOT/'dist/windows'/f'{name}.exe'],env)
    report={'app':app,'uv':subprocess.check_output([uv,'--version'],env=env,text=True).strip(),
            'system_site_packages':False,'isolated_python':True,'packages':packages,
            'cfg_opt_in':app!='emulator',
            'file':name+'.exe','bytes':(ROOT/'dist/windows'/f'{name}.exe').stat().st_size}
    (ROOT/'dist/windows'/f'{app}-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app',choices=['patcher','emulator','both'],default='both')
    args=parser.parse_args()
    if os.name!='nt':parser.error('Windows executables must be built on Windows.')
    (ROOT/'dist/windows').mkdir(exist_ok=True,parents=True)
    for app in (['patcher','emulator'] if args.app=='both' else [args.app]):build(app)


if __name__=='__main__':main()
