"""English-only desktop UI around the real patched ARM firmware."""
from pathlib import Path
import argparse
import json
import time
import traceback
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk
from ..engine import profiles,resource,decode_splash
from .. import theme
from .factory import create_core,original_path,camera_status,app_data

BG=theme.BG;FG=theme.FG;MUTED=theme.MUTED;GREEN=theme.ACCENT


class EmulatorApp:
    def __init__(self,window,firmware=None,data_dir=None,auto_start=True):
        self.window=window;self.data_dir=Path(data_dir) if data_dir else app_data()
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self.core=None;self.firmware_path=Path(firmware) if firmware else None
        self.paused=False;self.failed=False;self.in_boot=False;self.held_keys=set()
        self.last_flush=-1;self.last_step=time.monotonic();self.last_write=0;self.last_flash=None
        window.title('reGODOX | Native Firmware Emulator');window.configure(bg=BG);window.resizable(False,False)
        if resource('regodox.ico').is_file() and __import__('sys').platform=='win32':
            window.iconbitmap(str(resource('regodox.ico')))
        self.style=theme.setup(window)
        outer=ttk.Frame(window,padding=20);outer.grid()
        self.canvas=tk.Canvas(outer,width=368,height=448,bg='black',highlightthickness=1,
                              highlightbackground='#30394a',cursor='crosshair')
        self.canvas.grid(row=0,column=0,rowspan=2,padx=(0,22));self.display=self.canvas.create_image(0,0,anchor='nw')
        right=ttk.Frame(outer);right.grid(row=0,column=1,sticky='nsew')
        ttk.Label(right,text='reGODOX',font=('Segoe UI',22,'bold')).pack(anchor='w')
        ttk.Label(right,text='NATIVE FIRMWARE EMULATOR',foreground=GREEN,font=('Segoe UI',9)).pack(anchor='w',pady=(0,12))
        self.profile_list=profiles();self.selected=tk.StringVar(value=self.profile_list[0].label)
        self.models=ttk.Combobox(right,textvariable=self.selected,values=[p.label for p in self.profile_list],
                                 state='readonly',width=30)
        self.models.pack(fill='x',pady=(0,12));self.models.bind('<<ComboboxSelected>>',self.select_model)
        self.hold_button(right,'TEST  /  Space','test_pressed')
        self.hold_button(right,'Power  /  P','power_pressed')
        self.hold_button(right,'Wheel click  /  Enter','side_pressed')
        row=ttk.Frame(right);row.pack(fill='x',pady=(6,10))
        ttk.Button(row,text='↶ Left',command=lambda:self.rotate(-1)).pack(side='left',expand=True,fill='x',padx=(0,4))
        ttk.Button(row,text='Right ↷',command=lambda:self.rotate(1)).pack(side='left',expand=True,fill='x')
        self.connected=tk.BooleanVar(value=True)
        ttk.Checkbutton(right,text='Camera link (modeled)',bootstyle='success-round-toggle',variable=self.connected,
                        command=self.update_camera).pack(anchor='w',pady=(0,4))
        self.camera_note=ttk.Label(right,text='F/5.6  ·  ISO 400  ·  1/160',style='Muted.TLabel',wraplength=275)
        self.camera_note.pack(anchor='w',pady=(0,8))
        ttk.Label(right,text='Drag on screen to swipe.\nMouse wheel or ← → to rotate.\nMiddle mouse button clicks the wheel.',
                  style='Muted.TLabel').pack(anchor='w',pady=(0,10))
        controls=ttk.Frame(right);controls.pack(fill='x')
        self.pause_button=ttk.Button(controls,text='Pause',command=self.toggle_pause)
        self.pause_button.pack(side='left',expand=True,fill='x',padx=(0,4))
        ttk.Button(controls,text='Restart',command=self.restart).pack(side='left',expand=True,fill='x')
        ttk.Button(right,text='Open firmware…',bootstyle='info-outline',command=self.choose_image).pack(fill='x',pady=(6,3))
        ttk.Button(right,text='Save screenshot…',bootstyle='secondary-outline',command=self.screenshot).pack(fill='x',pady=3)
        self.info=ttk.Label(outer,text='Starting…',style='Muted.TLabel',wraplength=280)
        self.info.grid(row=1,column=1,sticky='sw',pady=(12,0))
        self.status=ttk.Label(outer,text='',style='Muted.TLabel',wraplength=690)
        self.status.grid(row=2,column=0,columnspan=2,sticky='w',pady=(14,0))
        ttk.Label(outer,text='Real ARM + LVGL pixels. Radio, GPIO, camera and idle timing are modeled.\n'
                  'Settings are saved locally and separately for every camera system.',
                  style='Muted.TLabel',wraplength=690).grid(row=3,column=0,columnspan=2,sticky='w',pady=(8,0))
        self.canvas.bind('<ButtonPress-1>',self.touch_down);self.canvas.bind('<B1-Motion>',self.touch_move)
        self.canvas.bind('<ButtonRelease-1>',self.touch_up)
        self.canvas.bind('<MouseWheel>',lambda e:self.rotate(1 if e.delta>0 else -1))
        self.canvas.bind('<ButtonPress-2>',lambda e:self.set_button('side_pressed',True))
        self.canvas.bind('<ButtonRelease-2>',lambda e:self.set_button('side_pressed',False))
        window.bind('<KeyPress>',self.key_down);window.bind('<KeyRelease>',self.key_up)
        window.bind('<FocusOut>',lambda e:self.release_inputs() if e.widget==window else None)
        window.protocol('WM_DELETE_WINDOW',self.close)
        if auto_start:window.after(50,self.boot);window.after(20,self.tick)

    def hold_button(self,parent,text,attribute):
        button=ttk.Button(parent,text=text,bootstyle='warning-outline' if attribute=='power_pressed' else 'secondary-outline');button.pack(fill='x',pady=3)
        def down(event):button.grab_set();self.set_button(attribute,True)
        def up(event):
            try:button.grab_release()
            except tk.TclError:pass
            self.set_button(attribute,False)
        button.bind('<ButtonPress-1>',down);button.bind('<ButtonRelease-1>',up)

    def set_button(self,name,down):
        if not self.core or self.in_boot:return
        if name=='power_pressed' and down and not self.core.powered:self.restart();return
        setattr(self.core,name,down)

    def release_inputs(self):
        self.held_keys.clear()
        if self.core:
            self.core.test_pressed=self.core.side_pressed=self.core.power_pressed=False
            x,y,_=self.core.touch;self.core.touch=(x,y,False)

    def key_down(self,event):
        key=event.keysym.lower()
        if key in ('left','right'):self.rotate(-1 if key=='left' else 1);return
        if key in self.held_keys:return
        self.held_keys.add(key)
        name={'space':'test_pressed','return':'side_pressed','p':'power_pressed'}.get(key)
        if name:self.set_button(name,True)

    def key_up(self,event):
        key=event.keysym.lower();self.held_keys.discard(key)
        name={'space':'test_pressed','return':'side_pressed','p':'power_pressed'}.get(key)
        if name:self.set_button(name,False)

    def rotate(self,delta):
        if self.core and self.core.powered and not self.failed:self.core.encoder_pending+=delta

    @staticmethod
    def point(event):return max(0,min(367,event.x)),max(0,min(447,event.y))

    def touch_down(self,event):
        if self.core:self.canvas.grab_set();self.core.touch=(*self.point(event),True)

    def touch_move(self,event):
        if self.core:self.core.touch=(*self.point(event),True)

    def touch_up(self,event):
        if self.core:self.core.touch=(*self.point(event),False)
        try:self.canvas.grab_release()
        except tk.TclError:pass

    def boot(self):
        if self.in_boot:return
        self.in_boot=True;self.release_inputs()
        try:
            p=next(p for p in self.profile_list if p.label==self.selected.get())
            path=self.firmware_path or original_path(p)
            from ..engine import identify
            data=path.read_bytes();p,_=identify(data)
            state=self.data_dir/f'flash-{p.id}.bin'
            core=create_core(data,flash=state.read_bytes() if state.exists() else None)
            core.initialize()
            self.core=core;self.state_file=state;self.selected.set(p.label)
            self.bank_pointer=core.bank_context()
            self.failed=False;self.paused=False;self.pause_button.configure(text='Pause')
            camera_status(core,self.connected.get())
            self.camera_note.configure(text='F/5.6  ·  ISO 400  ·  1/160' if p.camera_parameters
                else 'Exposure data unavailable in this stock firmware. CamLCD is disabled.')
            self.last_flash=core.flash_snapshot();self.last_step=time.monotonic();self.last_flush=-1
            self.status.configure(text=p.label+'  |  '+path.name)
            self.refresh()
        except Exception:self.error()
        finally:self.in_boot=False

    def update_camera(self):
        if self.core and not self.failed:
            try:camera_status(self.core,self.connected.get())
            except Exception:self.error()

    def select_model(self,event=None):
        self.persist();self.firmware_path=None;self.boot()

    def choose_image(self):
        path=filedialog.askopenfilename(title='Open supported Godox X3 firmware',filetypes=[('Firmware','*.bin')])
        if path:self.persist();self.firmware_path=Path(path);self.boot()

    def restart(self):self.persist();self.boot()

    def toggle_pause(self):
        self.paused=not self.paused;self.pause_button.configure(text='Resume' if self.paused else 'Pause')
        self.last_step=time.monotonic();self.release_inputs()

    def refresh(self):
        if not self.core:return
        if self.core.powered:
            frame=self.core.frame;c=self.bank_pointer;bank=f'P{self.core.word(c+16)+1}' if c else 'Stock'
            self.info.configure(text=f'{bank}  ·  {self.core.now/1000:.1f} s\nTEST fires: {self.core.flash_count}\n'
                                f'Display flushes: {self.core.flush_count}')
        else:frame=Image.new('RGB',(368,448));self.info.configure(text='Powered off. Press Power to restart.')
        self.photo=ImageTk.PhotoImage(frame);self.canvas.itemconfigure(self.display,image=self.photo)
        self.last_flush=self.core.flush_count

    def tick(self):
        started=time.monotonic()
        try:
            if self.core and not self.in_boot and not self.failed and not self.paused:
                now=time.monotonic();dt=max(20,min(100,int((now-self.last_step)*1000)//5*5))
                self.last_step=now;self.core.step(dt)
                if self.last_flush!=self.core.flush_count or not self.core.powered:self.refresh()
                if now-self.last_write>0.5:self.persist();self.last_write=now
        except Exception:self.error()
        self.window.after(max(1,20-int((time.monotonic()-started)*1000)),self.tick)

    def persist(self):
        if not self.core:return
        data=self.core.flash_snapshot()
        if data!=self.last_flash or not self.state_file.exists():
            from ..engine import save_atomic
            save_atomic(self.state_file,data);self.last_flash=data

    def screenshot(self):
        path=filedialog.asksaveasfilename(title='Save native display pixels',defaultextension='.png',
            initialfile='regodox-screen.png',filetypes=[('PNG','*.png')])
        if path and self.core:self.core.frame.save(path)

    def error(self):
        self.failed=True;detail=traceback.format_exc()
        (self.data_dir/'last-error.txt').write_text(detail,encoding='utf-8')
        self.status.configure(text='Stopped: '+detail.strip().splitlines()[-1])
        self.info.configure(text='Details saved to '+str(self.data_dir/'last-error.txt'))

    def close(self):
        if self.core and not self.failed:
            try:self.core.save();self.persist()
            except Exception:(self.data_dir/'last-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        self.window.destroy()


def main():
    parser=argparse.ArgumentParser(description='reGODOX native firmware emulator')
    parser.add_argument('firmware',nargs='?',type=Path)
    parser.add_argument('--model',choices=list('CNSFOL'),default='C')
    parser.add_argument('--smoke-test',type=Path)
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args();root=tk.Tk()
    if args.smoke_test:
        import tempfile
        root.withdraw()
        with tempfile.TemporaryDirectory(prefix='regodox-smoke-') as directory:
            app=EmulatorApp(root,data_dir=directory,auto_start=False)
            results=[]
            for p in profiles():
                app.selected.set(p.label);app.firmware_path=None;app.boot()
                if app.failed:
                    args.smoke_test.parent.mkdir(exist_ok=True,parents=True)
                    args.smoke_test.write_text(json.dumps({'ok':False,'model':p.id,
                        'error':(app.data_dir/'last-error.txt').read_text(encoding='utf-8')},indent=2))
                    app.close()
                    return
                assert app.core.bank_context()
                results.append(p.id)
            args.smoke_test.parent.mkdir(exist_ok=True,parents=True)
            args.smoke_test.write_text(json.dumps({'GUI_created':True,'models':results,'ok':True}),encoding='utf-8')
            app.close()
        return
    app=EmulatorApp(root,args.firmware,data_dir=args.data_dir)
    app.selected.set(next(p.label for p in profiles() if p.id==args.model))
    root.mainloop()


if __name__=='__main__':main()
