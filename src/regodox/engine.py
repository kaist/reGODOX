"""Apply the entire audited patch set; never infer compatibility from a filename."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile

from PIL import Image

WIDTH, HEIGHT, PAYLOAD_SIZE = 368, 448, 41232
PROTECTED_OFFSET = 0xEF000


def resource(name: str):
    return files('regodox.resources').joinpath(name)


@dataclass(frozen=True)
class Profile:
    id: str
    brand: str
    version: str
    original_name: str
    output_name: str
    size: int
    original_sha256: str
    default_sha256: str
    patched_fingerprint: str
    pixel_offset: int
    descriptor_offset: int
    camera_parameters: bool
    camlcd_default: bool
    camlcd_menu: bool
    variant_code: int
    status_parser: int
    status_packet_size: int
    native: dict[str,int]
    ram: dict[str,int]

    @property
    def label(self):
        return f'{self.brand} · X3-{self.id} {self.version}'


@lru_cache
def profiles() -> tuple[Profile, ...]:
    return tuple(Profile(**p) for p in json.loads(resource('profiles.json').read_text(encoding='utf-8')))


@lru_cache
def recipe(model: str):
    return json.loads(resource(f'recipes/{model}.json').read_text(encoding='utf-8'))


def fingerprint(data: bytes, profile: Profile) -> str:
    masked=bytearray(data)
    masked[profile.pixel_offset:profile.pixel_offset+PAYLOAD_SIZE]=bytes(PAYLOAD_SIZE)
    return hashlib.sha256(masked).hexdigest()


def identify(data: bytes) -> tuple[Profile, str]:
    sha=hashlib.sha256(data).hexdigest()
    for p in profiles():
        if len(data)!=p.size:continue
        if sha==p.original_sha256:return p,'original'
        if fingerprint(data,p)==p.patched_fingerprint:
            header,size,pointer=struct.unpack_from('<III',data,p.descriptor_offset)
            if (header,size,pointer)==(8|WIDTH<<10|HEIGHT<<21,PAYLOAD_SIZE,0x08004800+p.pixel_offset):
                return p,'regodox'
    raise ValueError('Unsupported or modified firmware. Choose an exact supported original BIN '
                     'or a reGODOX build created by this release. No file was changed.')


def encode_splash(image: Image.Image) -> bytes:
    if image.size!=(WIDTH,HEIGHT) or image.mode!='P' or max(image.tobytes())>3:
        raise ValueError('Splash must be a 368 × 448 indexed image with four palette indices.')
    palette=image.getpalette();pixels=image.tobytes();payload=bytearray()
    for i in range(4):
        r,g,b=palette[i*3:i*3+3];payload.extend((b,g,r,255))
    for i in range(0,len(pixels),4):
        a,b,c,d=pixels[i:i+4];payload.append(a<<6|b<<4|c<<2|d)
    assert len(payload)==PAYLOAD_SIZE
    return bytes(payload)


def decode_splash(payload: bytes) -> Image.Image:
    if len(payload)!=PAYLOAD_SIZE:raise ValueError('Invalid splash data size.')
    palette=[];indices=bytearray()
    for i in range(4):
        b,g,r,a=payload[4*i:4*i+4]
        if a!=255:raise ValueError('Unsupported transparent palette entry.')
        palette.extend((r,g,b))
    for b in payload[16:]:indices.extend(((b>>6)&3,(b>>4)&3,(b>>2)&3,b&3))
    image=Image.frombytes('P',(WIDTH,HEIGHT),bytes(indices))
    image.putpalette(palette+[0]*756)
    return image


def default_splash() -> Image.Image:
    return decode_splash(resource('default-splash.bin').read_bytes())


def build(data: bytes, splash: Image.Image | None = None) -> tuple[bytes, dict]:
    profile,kind=identify(data)
    patched=bytearray(data)
    if kind=='original':
        for part in recipe(profile.id)['patches']:
            at=part['offset'];before=bytes.fromhex(part['before']);after=bytes.fromhex(part['after'])
            if len(before)!=len(after) or at<0 or at+len(after)>PROTECTED_OFFSET:
                raise ValueError('Invalid patch recipe bounds.')
            if data[at:at+len(before)]!=before:raise ValueError('Original-byte assertion failed.')
            patched[at:at+len(after)]=after
    payload=resource('default-splash.bin').read_bytes() if splash is None else encode_splash(splash)
    patched[profile.pixel_offset:profile.pixel_offset+PAYLOAD_SIZE]=payload
    result=bytes(patched)
    if len(result)!=len(data) or result[PROTECTED_OFFSET:]!=data[PROTECTED_OFFSET:]:
        raise ValueError('Protected firmware or storage region changed.')
    detected,state=identify(result)
    if detected!=profile or state!='regodox':raise ValueError('Output verification failed.')
    if splash is None and hashlib.sha256(result).hexdigest()!=profile.default_sha256:
        raise ValueError('Default build does not match the verified release.')
    if encode_splash(decode_splash(payload))!=payload:raise ValueError('Splash round-trip failed.')
    return result,{'model':profile.id,'brand':profile.brand,'version':profile.version,
        'input_kind':kind,'input_sha256':hashlib.sha256(data).hexdigest(),
        'output_sha256':hashlib.sha256(result).hexdigest(),'output_name':profile.output_name,
        'all_patches_applied':True,'protected_region_unchanged':True,
        'CamLCD_default':profile.camlcd_default,'CamLCD_menu':profile.camlcd_menu,
        'camera_parameters':profile.camera_parameters,'splash':[WIDTH,HEIGHT,4]}


def save_atomic(destination: Path, data: bytes, source: Path | None = None):
    destination=Path(destination)
    if source is not None and destination.resolve()==Path(source).resolve():
        raise ValueError('Choose a new output file. The input firmware cannot be overwritten.')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False,suffix='.tmp') as f:
            temporary=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
        if temporary.read_bytes()!=data:raise OSError('Saved file verification failed.')
        os.replace(temporary,destination);temporary=None
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
