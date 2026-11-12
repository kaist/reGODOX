"""Validate and assemble the same assets locally and in GitHub Releases."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from regodox.engine import profiles

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(path,entries):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for source,name in entries:
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,source.read_bytes())


def main():
    release=ROOT/'dist/release';release.mkdir(parents=True,exist_ok=True)
    firmware=[]
    for p in profiles():
        path=ROOT/'dist/firmware'/p.output_name
        if sha(path)!=p.default_sha256:raise RuntimeError('Firmware verification failed: '+p.id)
        firmware.append((path,'firmware/'+path.name))
    smoke=json.loads((ROOT/'dist/windows/executable-smoke.json').read_text())
    if not smoke['emulator']['ok'] or set(smoke['emulator']['models'])!=set('CNSFOL'):
        raise RuntimeError('Both actual executable smoke tests must pass first.')
    if not smoke['patcher']['all_patches_applied']:raise RuntimeError('Patcher smoke test failed.')
    apps=[(ROOT/'dist/windows'/name,name) for name in
          ('reGODOX-Firmware-Studio.exe','reGODOX-Emulator.exe')]
    for source,name in apps:
        if smoke.get('executables',{}).get(name)!=sha(source):
            raise RuntimeError('Executable changed since smoke test: '+name)
    docs=[(ROOT/name,name) for name in ('README.md','README.ru.md','LICENSE','THIRD_PARTY_NOTICES.md')]
    images=[(p,'docs/images/'+p.name) for p in sorted((ROOT/'docs/images').glob('*.png'))]
    firmware_docs=[(ROOT/'dist/firmware/SHA256SUMS.txt','firmware/SHA256SUMS.txt')]
    reports=[(p,'build-reports/'+p.name) for p in sorted((ROOT/'dist/windows').glob('*.json'))]
    archive(release/'reGODOX-Firmware.zip',firmware+firmware_docs+docs+images)
    archive(release/'reGODOX-Windows-Bundle.zip',apps+firmware+firmware_docs+docs+images+reports)
    for source,name in apps+docs:shutil.copy2(source,release/name)
    assets=[release/name for _,name in apps+docs]+[
        release/'reGODOX-Firmware.zip',release/'reGODOX-Windows-Bundle.zip']
    (release/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(assets)),encoding='utf-8')
    print('Release assets verified: '+', '.join(p.name for p in assets))


if __name__=='__main__':main()
