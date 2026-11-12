from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import tkinter as tk
import pytest
from PIL import Image
from regodox import engine
from regodox.gui import FirmwareStudio

pytestmark=pytest.mark.gui
ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def studio(tk_window):
    root=tk_window;app=FirmwareStudio(root)
    yield root,app
    # Restore the Windows WNDPROC before destroying the window.
    root.tk.call(root.protocol('WM_DELETE_WINDOW'))


def test_gui_applies_every_patch_to_originals(studio,tmp_path):
    root,app=studio
    for profile in engine.profiles():
        source=ROOT/'firmware/original'/profile.original_name
        app.open_path(source);root.update()
        assert app.profile==profile and str(app.save_button['state'])=='normal'
        dest=tmp_path/profile.output_name;report=app.save_to(dest)
        assert report['output_sha256']==profile.default_sha256
        assert engine.identify(dest.read_bytes())==(profile,'regodox')
        with pytest.raises(ValueError):app.save_to(source)


def test_gui_live_crop_palette_and_custom_build(studio,tmp_path):
    root,app=studio
    im=Image.new('RGB',(900,600),'#fa4080')
    for x in range(450):
        for y in range(600):im.putpixel((x,y),(20,130,220))
    p=tmp_path/'custom.png';im.save(p);app.open_path(p);root.update()
    initial=app.preview.convert('RGB').tobytes()
    app.zoom.set(2);app.center=(100,300);app.render()
    assert app.preview.convert('RGB').tobytes()!=initial
    assert len(app.preview.getcolors())<=4
    app.open_path(ROOT/'firmware/original'/engine.profiles()[0].original_name)
    dest=tmp_path/'custom.bin';app.save_to(dest)
    profile,_=engine.identify(dest.read_bytes())
    payload=dest.read_bytes()[profile.pixel_offset:profile.pixel_offset+engine.PAYLOAD_SIZE]
    assert engine.decode_splash(payload).convert('RGB').tobytes()==app.preview.convert('RGB').tobytes()
    app.use_default();assert app.preview.convert('RGB').tobytes()==engine.default_splash().convert('RGB').tobytes()


@pytest.mark.skipif(sys.platform!='win32',reason='Windows native file drops')
def test_native_unicode_drop(studio,tmp_path):
    import ctypes
    import struct
    from ctypes import wintypes as w
    root,app=studio;p=tmp_path/'image-\u043a\u043e\u0442.png'
    Image.new('RGB',(600,500),'#5badea').save(p)
    kernel,user=ctypes.windll.kernel32,ctypes.windll.user32
    kernel.GlobalAlloc.argtypes=[ctypes.c_uint,ctypes.c_size_t];kernel.GlobalAlloc.restype=ctypes.c_void_p
    kernel.GlobalLock.argtypes=[ctypes.c_void_p];kernel.GlobalLock.restype=ctypes.c_void_p
    kernel.GlobalUnlock.argtypes=[ctypes.c_void_p]
    user.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
    names=(str(p)+'\0\0').encode('utf-16-le');blob=struct.pack('<IiiII',20,0,0,0,1)+names
    handle=kernel.GlobalAlloc(0x42,len(blob));pointer=kernel.GlobalLock(handle)
    ctypes.memmove(pointer,blob,len(blob));kernel.GlobalUnlock(handle)
    user.SendMessageW(app.drop_hwnd,0x233,handle,0);root.update()
    assert app.image_label['text']==p.name
    assert app.preview.convert('RGB').getpixel((0,0))==(91,173,234)
