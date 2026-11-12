"""Capture real Tk windows with PrintWindow and compose the README cover."""
from pathlib import Path
import ctypes as c
from ctypes import wintypes as w
import tempfile
import tkinter as tk
from PIL import Image,ImageDraw,ImageFont
from regodox.gui import FirmwareStudio
from regodox.emulator.app import EmulatorApp
from regodox.engine import profiles,default_splash

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/images'


def capture(root,path):
    root.update_idletasks();root.update()
    user=c.windll.user32;gdi=c.windll.gdi32
    user.GetParent.argtypes=[w.HWND];user.GetParent.restype=w.HWND
    user.GetWindowDC.argtypes=[w.HWND];user.GetWindowDC.restype=w.HDC
    gdi.CreateCompatibleDC.argtypes=[w.HDC];gdi.CreateCompatibleDC.restype=w.HDC
    gdi.CreateCompatibleBitmap.argtypes=[w.HDC,c.c_int,c.c_int];gdi.CreateCompatibleBitmap.restype=w.HBITMAP
    gdi.SelectObject.argtypes=[w.HDC,w.HGDIOBJ];gdi.SelectObject.restype=w.HGDIOBJ
    user.PrintWindow.argtypes=[w.HWND,w.HDC,w.UINT]
    gdi.GetDIBits.argtypes=[w.HDC,w.HBITMAP,w.UINT,w.UINT,c.c_void_p,c.c_void_p,w.UINT]
    gdi.DeleteObject.argtypes=[w.HGDIOBJ];gdi.DeleteDC.argtypes=[w.HDC]
    user.ReleaseDC.argtypes=[w.HWND,w.HDC]
    hwnd=user.GetParent(root.winfo_id()) or root.winfo_id()
    rect=w.RECT();user.GetWindowRect(hwnd,c.byref(rect))
    width,height=rect.right-rect.left,rect.bottom-rect.top
    dc=user.GetWindowDC(hwnd);memory=gdi.CreateCompatibleDC(dc)
    bitmap=gdi.CreateCompatibleBitmap(dc,width,height);old=gdi.SelectObject(memory,bitmap)
    try:
        if not user.PrintWindow(hwnd,memory,2):raise RuntimeError('PrintWindow failed')
        class Header(c.Structure):
            _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),
                      ('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),
                      ('x',w.LONG),('y',w.LONG),('used',w.DWORD),('important',w.DWORD)]
        header=Header(40,width,-height,1,32,0,0,0,0,0,0)
        pixels=c.create_string_buffer(width*height*4)
        if not gdi.GetDIBits(memory,bitmap,0,height,pixels,c.byref(header),0):
            raise RuntimeError('GetDIBits failed')
        Image.frombytes('RGB',(width,height),pixels.raw,'raw','BGRX').save(path)
    finally:
        gdi.SelectObject(memory,old);gdi.DeleteObject(bitmap);gdi.DeleteDC(memory);user.ReleaseDC(hwnd,dc)


def cover():
    image=Image.new('RGB',(1440,690),'#101319');draw=ImageDraw.Draw(image)
    def font(size,bold=False):
        return ImageFont.truetype('C:/Windows/Fonts/'+('segoeuib.ttf' if bold else 'segoeui.ttf'),size)
    draw.text((64,65),'reGODOX',font=font(86,True),fill='#f2d674')
    draw.text((69,189),'Make your X3 your own.',font=font(29),fill='#f1f5fa')
    for y,text in enumerate(['Four independent presets','Custom splash artwork','Live Canon / Nikon exposure','Native firmware emulator']):
        draw.text((72,283+y*44),text,font=font(22),fill='#afbdce')
    draw.text((72,581),'C  /  N  /  S  /  F  /  O  /  L',font=font(22,True),fill='#7cddba')
    for x,name,title in [(585,'c-splash.png','YOUR SPLASH'),(865,'presets.png','YOUR PRESETS'),
                         (1145,'camera-info.png','CAMERA INFO')]:
        frame=Image.open(OUT/name).convert('RGB');frame.thumbnail((244,425))
        draw.rounded_rectangle((x-8,151,x+252,151+frame.height+16),radius=18,fill='#2b3442')
        image.paste(frame,(x,159))
        draw.text((x,111),title,font=font(16,True),fill='#a9b8ca')
    image.save(OUT/'cover.png')


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    root=tk.Tk();studio=FirmwareStudio(root)
    studio.open_path(ROOT/'firmware/original'/profiles()[0].original_name)
    studio.render();capture(root,OUT/'patcher.png')
    root.tk.call(root.protocol('WM_DELETE_WINDOW'))
    with tempfile.TemporaryDirectory(prefix='regodox-docs-') as directory:
        root=tk.Tk();app=EmulatorApp(root,data_dir=directory,auto_start=False)
        app.selected.set(profiles()[1].label);app.boot()
        if app.failed:raise RuntimeError(app.status['text'])
        capture(root,OUT/'emulator.png');app.close()
    default_splash().save(OUT/'splash.png');cover()


if __name__=='__main__':main()
