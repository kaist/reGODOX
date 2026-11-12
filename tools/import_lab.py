"""Import the audited release from a lab directory; not needed to build this repo.

Usage: python tools/import_lab.py PATH_TO_LAB
Recipes contain original-byte assertions and complete non-image patch payloads.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
LAB = Path(sys.argv[1]).resolve()
sys.path.insert(0,str(LAB/'analysis/regodox'))
from port import Port
RES = ROOT/'src/regodox/resources'
RES.mkdir(parents=True,exist_ok=True)
(RES/'recipes').mkdir(exist_ok=True)
(ROOT/'firmware/original').mkdir(parents=True,exist_ok=True)
(ROOT/'firmware/src').mkdir(parents=True,exist_ok=True)
(ROOT/'src/regodox/emulator/cores').mkdir(parents=True,exist_ok=True)
(ROOT/'docs/images').mkdir(parents=True,exist_ok=True)
FW = 0x08004800
profiles=[]
reference_payload=None
for letter in 'CNSFOL':
    row=json.loads((LAB/'analysis/variants'/letter/'inspection.json').read_text())
    source=LAB/row['file'];original=source.read_bytes()
    final=LAB/'output'/('regodox_'+source.name);patched=final.read_bytes()
    meta=json.loads(final.with_suffix('.json').read_text())
    assert hashlib.sha256(original).hexdigest()==row['sha256']
    assert hashlib.sha256(patched).hexdigest()==meta['sha256']
    assert len(original)==len(patched) and original[0xef000:]==patched[0xef000:]
    pixel=int(meta['splash']['pixels'],16)-FW
    descriptor=int(meta['splash']['descriptor'],16)-FW
    payload=patched[pixel:pixel+41232]
    if reference_payload is None:reference_payload=payload
    assert payload==reference_payload
    # Merge adjacent changes separated by <=16 unchanged bytes, excluding image.
    changes=[i for i,(a,b) in enumerate(zip(original,patched)) if a!=b and not pixel<=i<pixel+41232]
    spans=[]
    for i in changes:
        if spans and i-spans[-1][1]<=16 and not spans[-1][0]<pixel<i:
            spans[-1][1]=i+1
        else:spans.append([i,i+1])
    parts=[{'offset':a,'before':original[a:b].hex(),'after':patched[a:b].hex()} for a,b in spans]
    normalized=bytearray(patched);normalized[pixel:pixel+41232]=bytes(41232)
    p={'id':letter,'brand':row['brand'],'version':row['version'],'original_name':source.name,
       'output_name':final.name,'size':len(original),'original_sha256':row['sha256'],
       'default_sha256':meta['sha256'],
       'patched_fingerprint':hashlib.sha256(normalized).hexdigest(),
       'pixel_offset':pixel,'descriptor_offset':descriptor,
       'camera_parameters':letter in 'CN','camlcd_default':letter in 'CN','camlcd_menu':letter in 'CN',
       'variant_code':{'C':1,'N':2,'S':3,'O':4,'F':5,'L':7}[letter],
       'status_parser':{'C':0x08012d8c,'O':0x08012ce8}.get(letter,0x08012d28),
       'status_packet_size':26 if letter=='C' else 25}
    port=Port(letter)
    p['native']={name:port.address(address) for name,address in {
        'splash':0x08006134,'m_step':0x0801a38c,'ttl_step':0x0801a294,
        'gpio_read':0x08022eb4,'obj_valid':0x080303b8,'scroll_to_view':0x0803118e,
        'OLED_command':0x0801a234,'text_set':0x0802d33c}.items()}
    p['ram']={name:port.address(address) for name,address in {
        'groups':0x20000b68,'channel':0x20000054,'wireless_id':0x20000055,
        'modeling_light':0x200003df,'sound':0x20000484,'step':0x200003e1,
        'menu':0x200003e7,'page':0x200004c4,'main_action':0x200003e4}.items()}
    recipe={'schema':1,'profile':letter,'patches':parts,'symbols':meta['symbols'],
            'step_symbols':meta.get('step_symbols',{})}
    if letter=='C':
        recipe['step_symbols']=json.loads((LAB/'analysis/step_extension_symbols.json').read_text())
    (RES/'recipes'/f'{letter}.json').write_text(json.dumps(recipe,indent=2),encoding='utf-8')
    shutil.copy2(source,ROOT/'firmware/original'/source.name)
    profiles.append(p)
    # Preserve the tested core's native addresses. Inputs/symbols become in-memory
    # parameters so no analysis folder, absolute lab path or sidecar is needed.
    text=(LAB/'analysis/regodox'/letter/'native_core.py').read_text(encoding='utf-8')
    text=re.sub(r'^ROOT=.*\nDEFAULT_IMAGE=.*\n','',text,flags=re.M)
    text=text.replace('def __init__(self,image_path=DEFAULT_IMAGE,flash=None,verbose=False,simulate_idle=False):',
                      'def __init__(self,image_bytes,symbols=None,flash=None,verbose=False,simulate_idle=False):')
    text=text.replace('self.image_path=Path(image_path);self.image_bytes=self.image_path.read_bytes()',
                      'self.image_bytes=bytes(image_bytes)')
    text=re.sub(r"        manifest=self.image_path.with_suffix\('.json'\)\n        self.symbols=[^\n]+",
                '        self.symbols=dict(symbols or {})',text)
    text=re.sub(r"raise ValueError\('[^\n]*Godox[^\n]*'\)",
                "raise ValueError('Unsupported Godox X3 variant or firmware version.')",text)
    (ROOT/'src/regodox/emulator/cores'/f'{letter.lower()}.py').write_text(text,encoding='utf-8')
    curated=['preset_count_banks.c','preset_popup_count.c','preset_count_ui.c','preset_drawer.c',
             'camera_sheet.c','camlcd.c','step_extension.c','popup_v5_addresses.h',
             'preset_count.ld','step_extension.ld','address-map.json']
    dest=ROOT/'firmware/src'/letter;dest.mkdir(exist_ok=True)
    for name in curated:
        path=LAB/'analysis/regodox'/letter/name
        if not path.exists() and letter=='C':path=LAB/'analysis'/name
        if path.exists():shutil.copy2(path,dest/name)
    for name in ['splash','settings']:
        path=LAB/'output'/f'regodox-{letter}-{name}.png'
        if path.exists():shutil.copy2(path,ROOT/'docs/images'/f'{letter.lower()}-{name}.png')
(RES/'profiles.json').write_text(json.dumps(profiles,indent=2),encoding='utf-8')
(RES/'default-splash.bin').write_bytes(reference_payload)
shutil.copy2(LAB/'analysis/images/regodox-default-4color.png',RES/'default-splash.png')
shutil.copy2(LAB/'splash-tool/assets/splash.ico',RES/'regodox.ico')
shutil.copy2(LAB/'analysis/popup_v5_banks.s',ROOT/'firmware/src/presets.s')
shutil.copy2(LAB/'analysis/images/regodox-v2-prompt.txt',ROOT/'docs/artwork-prompt.txt')
for src,name in [('nikon-emulator-preset-drawer-focus.png','presets.png'),
                 ('nikon-emulator-step-menu.png','step.png'),
                 ('nikon-emulator-camera-pipeline.png','camera-info.png'),
                 ('nikon-emulator-camlcd-on.png','camlcd.png')]:
    path=LAB/'output'/src
    if path.exists():shutil.copy2(path,ROOT/'docs/images'/name)
print('Imported six originals, asserted binary recipes, native cores and audit sources.')
