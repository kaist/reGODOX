"""Compare identical native workloads with/without instruction counting."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import tkinter as tk
from PIL import ImageTk
from regodox.engine import profiles
from regodox.emulator.factory import create_core,original_path,camera_status


def measure(profile,fast):
    m=create_core(original_path(profile).read_bytes(),fast=fast,simulate_idle=False)
    started=time.perf_counter();m.initialize();boot=time.perf_counter()-started
    flush_time=0.0
    for address,callback in list(m.hooks.items()):
        if callback.__name__=='flush':
            def flush(callback=callback):
                nonlocal flush_time
                before=time.perf_counter()
                try:callback()
                finally:flush_time+=time.perf_counter()-before
            m.hooks[address]=flush
    camera_status(m);started=time.perf_counter()
    for _ in range(50):m.step()
    idle=time.perf_counter()-started;idle_pixels=hashlib.sha256(m.frame.tobytes()).hexdigest()
    started=time.perf_counter()
    for y in range(420,135,-15):m.touch=(184,y,True);m.step()
    m.touch=(184,135,False)
    for _ in range(30):m.step()
    drawer=time.perf_counter()-started
    root=tk.Tk();root.withdraw();before=time.perf_counter()
    for _ in range(50):
        photo=ImageTk.PhotoImage(m.frame);root.update_idletasks()
    tk_time=(time.perf_counter()-before)/50;del photo;root.destroy()
    return {'boot_seconds':boot,'one_second_idle_wall_seconds':idle,'drawer_wall_seconds':drawer,
        'framebuffer_conversion_seconds':flush_time,'tk_frame_seconds':tk_time,
        'idle_pixels':idle_pixels,'drawer_pixels':hashlib.sha256(m.frame.tobytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=list('CNSFOL'),default='C')
    parser.add_argument('--output',type=Path,default=Path('build/emulator-benchmark.json'))
    args=parser.parse_args();p=next(p for p in profiles() if p.id==args.model)
    reference=measure(p,False);optimized=measure(p,True)
    for key in ('idle_pixels','drawer_pixels'):
        if reference[key]!=optimized[key]:raise RuntimeError('Native render differs: '+key)
    report={'model':p.id,'reference':reference,'optimized':optimized,'identical_native_pixels':True,
        'idle_speedup':reference['one_second_idle_wall_seconds']/optimized['one_second_idle_wall_seconds']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
