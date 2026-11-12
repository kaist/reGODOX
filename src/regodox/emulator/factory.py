"""Firmware preparation, native-core dispatch and modeled camera status."""
from pathlib import Path
import sys
from .. import engine
from .cores import c,n,s,f,o,l

MODULES={'C':c,'N':n,'S':s,'F':f,'O':o,'L':l}


def original_path(profile: engine.Profile) -> Path:
    if getattr(sys,'frozen',False):
        return Path(sys._MEIPASS)/'originals'/profile.original_name
    return Path(__file__).resolve().parents[3]/'firmware/original'/profile.original_name


def create_core(data: bytes,flash=None,simulate_idle=True,fast=True):
    profile,kind=engine.identify(data)
    if kind=='original':data,_=engine.build(data)
    core=MODULES[profile.id].NativeCore(data,symbols=engine.recipe(profile.id)['symbols'],
                                      flash=flash,simulate_idle=simulate_idle)
    core.profile=profile
    core.fast_execution=fast
    return core


def camera_status(core,connected=True,iso=0x58,aperture=0x30,shutter=0x73):
    p=core.profile;packet=bytearray(p.status_packet_size)
    packet[0]=0xb0;packet[1]=1;packet[3]=aperture;packet[4]=iso
    packet[5]=0x84;packet[6]=shutter;packet[7]=p.variant_code
    packet[8]=int(connected);packet[9]=1
    for i in (14,16,18,20,22):packet[i]=6
    packet[-1]=(0xb1+sum(packet[1:-1]))&255
    for value in packet:core.call(p.status_parser,value)


def app_data() -> Path:
    import os
    if sys.platform=='win32':base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
    else:base=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    return base/'regodox/emulator'
