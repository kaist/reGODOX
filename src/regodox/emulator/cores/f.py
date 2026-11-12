"""Godox X3 UI running native Thumb/LVGL code in Unicorn.

Hardware boundaries are modeled; this is not a cycle-accurate MCU emulator.
"""
from pathlib import Path
import struct,time,json,sys
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *
from PIL import Image
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB

STOP=0x080ff000
class NativeCore:
    def __init__(self,image_bytes,symbols=None,flash=None,verbose=False,simulate_idle=False):
        self.image_bytes=bytes(image_bytes)
        anchors={134400012: '38b5174c20780028', 134420768: '10b5eaf76dfc0e49', 134431892: '2de9f14f86b0ff4c'}
        if len(self.image_bytes)!=1016340 or any(self.image_bytes[a-0x08004800:a-0x08004800+8].hex()!=v for a,v in anchors.items()):
            raise ValueError('Unsupported Godox X3 variant or firmware version.')
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.u.mem_map(0x08000000,0x100000)
        self.u.mem_map(0x20000000,0x80000)
        self.u.mem_map(0x40000000,0x40000)
        self.u.mem_map(0xe0000000,0x100000)
        self.u.mem_map(0x6c000000,4096)
        self.u.mem_write(0x08000000,b'\xff'*0x100000)
        self.u.mem_write(0x08004800,self.image_bytes)
        if flash is not None:
            if len(flash)!=0x4000:raise ValueError('Expected 16 KiB virtual flash snapshot')
            self.u.mem_write(0x080f4000,bytes(flash))
        self.symbols=dict(symbols or {})
        self.simulate_idle=simulate_idle and 'camlcd_dim_service' in self.symbols
        self.now=0;self.touch=(0,0,False);self.flash_count=0;self.constructing=True
        self.test_pressed=False;self.side_pressed=False;self.power_pressed=False;self.unlocked=False
        self.encoder_pending=0;self.powered=True;self.verbose=verbose;self.radio_commands=0;self.null_focus_queries=0
        self.frame=Image.new('RGB',(368,448));self.flush_count=0
        self.hooks={0x08004ad8:self.runtime_done,0x0801c200:self.noop,
          0x0801bfe6:self.noop,0x0801c000:self.noop,0x0803b92c:self.noop,
          0x08035824:self.noop,0x0801c080:self.flush,0x08037594:self.touch_packet,
          0x080333c0:self.tick,0x08016f00:self.test_flash,0x0800b6d4:self.focus_guard,
          0x080217d0:self.unlock,0x08021698:self.lock,0x08021714:self.erase,0x08021918:self.program,
          0x0801fdc4:self.encoder_read,0x08035ef0:self.power_off,0x0801451c:self.noop,0x080392a4:self.noop,
          0x0801184c:self.radio,0x080117e8:self.radio,0x0802ec62:self.empty_focus_group}
        if self.simulate_idle:self.hooks[0x0801a11c]=self.noop # physical OLED command boundary
        for a,fn in self.hooks.items():self.u.hook_add(UC_HOOK_CODE,lambda u,pc,n,d:self.hooks[pc](),begin=a,end=a)
        try:
            self.u.reg_write(UC_ARM_REG_C1_C0_2,0xf<<20)
            self.u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
        except Exception:pass
    def r(self,n):return self.u.reg_read([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3][n])
    def word(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
    def put(self,a,v):self.u.mem_write(a,struct.pack('<I',v))
    def ret(self,v=0):self.u.reg_write(UC_ARM_REG_R0,v);self.u.reg_write(UC_ARM_REG_PC,self.u.reg_read(UC_ARM_REG_LR))
    def noop(self):self.ret()
    def focus_guard(self):
        if self.constructing:self.ret()
    def empty_focus_group(self):
        # Component bootstrap lacks some physical boot focus transitions.
        # Preserve the native function for every actual object; a missing
        # focus has no group. Counted/documented as an emulator compatibility shim.
        if not self.r(0):self.null_focus_queries+=1;self.ret(0)
    def runtime_done(self):self.u.emu_stop()
    def tick(self):self.ret(self.now&0xffffffff)
    def test_flash(self):self.flash_count+=1;self.ret()
    def radio(self):self.radio_commands+=1;self.ret()
    def power_off(self):
        # Stock shutdown has already saved settings. Stop at deep-sleep entry.
        self.powered=False;self.u.reg_write(UC_ARM_REG_PC,STOP)
    def unlock(self):self.unlocked=True;self.ret()
    def lock(self):self.unlocked=False;self.ret()
    def erase(self):
        address=self.r(0)&~2047
        if not self.unlocked or not (0x080f4000<=address<0x080f6000 or address==0x080f7800):
            raise RuntimeError(f'Unexpected flash erase {address:08x}')
        self.u.mem_write(address,b'\xff'*2048);self.ret(3)
    def program(self):
        address,buf,size=self.r(0),self.r(1),self.r(2)
        if not self.unlocked or not (0x080f4000<=address and address+size<=0x080f6000 or 0x080f7800<=address and address+size<=0x080f8000):
            raise RuntimeError(f'Unexpected flash write {address:08x}/{size}')
        before=bytes(self.u.mem_read(address,size));after=bytes(self.u.mem_read(buf,size))
        if any((a&b)!=b for a,b in zip(before,after)):self.ret(0);return
        self.u.mem_write(address,after);self.ret(1)
    def encoder_read(self):
        # Supply only the hardware quadrature delta, then execute the native
        # encoder callback (including PB15 press, LVGL state and acceleration).
        delta=max(-8,min(8,self.encoder_pending));self.encoder_pending-=delta
        self.u.mem_write(0x2000003b,bytes([delta&255]))
    def touch_packet(self):
        # CHSC report delivered through the firmware's I2C read boundary.
        # The ORIGINAL 0x08035060 interprets it and updates LVGL/state flags.
        p,n=self.r(1),self.r(2);x,y,pressed=self.touch
        if n!=8:raise RuntimeError(f'Unsupported CHSC transaction size: {n}')
        self.u.mem_write(p,bytes([0xff,int(pressed),x&255,y&255,0,((x>>8)&15)|(((y>>8)&15)<<4),0,0]))
        self.ret(0)
    def flush(self):
        driver,area,pixels=self.r(0),self.r(1),self.r(2)
        x1,y1,x2,y2=struct.unpack('<4i',self.u.mem_read(area,16))
        assert 0<=x1<=x2<368 and 0<=y1<=y2<448,(x1,y1,x2,y2)
        w,h=x2-x1+1,y2-y1+1
        data=bytes(self.u.mem_read(pixels,w*h*2))
        self.frame.paste(Image.frombytes('RGB',(w,h),data,'raw','BGR;16'),(x1,y1))
        self.flush_count+=1
        # Tail-call the actual lv_disp_flush_ready with the original LR.
        self.u.reg_write(UC_ARM_REG_R0,driver)
        self.u.reg_write(UC_ARM_REG_PC,0x080280f9)
    def call(self,a,*args,count=100000000):
        self.u.reg_write(UC_ARM_REG_SP,0x20070000);self.u.reg_write(UC_ARM_REG_LR,STOP|1)
        for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):self.u.reg_write(r,v)
        t=time.monotonic()
        try:
            if getattr(self,'fast_execution',False) and count==100000000:
                from ..execution import run
                run(self.u,a|1,STOP)
            else:self.u.emu_start(a|1,STOP,count=count)
        except Exception as e:raise RuntimeError(f'At PC=0x{self.u.reg_read(UC_ARM_REG_PC):08x}, LR=0x{self.u.reg_read(UC_ARM_REG_LR):08x}, args={[hex(self.r(n)) for n in range(4)]}, calling 0x{a:08x}: {e}') from e
        pc=self.u.reg_read(UC_ARM_REG_PC)
        if pc not in (STOP,0x08004ad8):raise RuntimeError(f'Instruction limit at 0x{pc:08x}, call 0x{a:08x}, {time.monotonic()-t:.2f}s')
        return self.r(0)
    def initialize(self):
        for a in (0x08004a14,0x08011284,0x0802c80c,0x08031920,0x0803196c):
            if self.verbose:print(f'init {a:08x}',flush=True)
            self.call(a)
        self.u.mem_write(0x20000033,bytes([5])) # Canon variant read from absent bootloader metadata
        self.put(0x20000044,60000);self.put(0x20000048,60000);self.put(0x20000050,60000)
        self.u.mem_write(0x200000fc,struct.pack('<H',60000));self.put(0x2000004c,60000)
        self.call(0x0800ba38)
        if self.verbose:print('build native main screen',flush=True)
        self.call(0x08034494,0)
        self.constructing=False
        self.call(0x080357dc)
        entry=next(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(self.image_bytes[0x08034040-0x08004800:0x08034044-0x08004800],0x08034040))
        self.call(int(entry.op_str[1:],16))
        self.call(0x080334a4)
        if self.verbose:print('frame',self.flush_count,flush=True)
    def step(self,dt=20):
        if not self.powered:return
        if self.simulate_idle and not (self.touch[2] or self.test_pressed or self.power_pressed or self.side_pressed or self.encoder_pending):
            # Component model: inactivity counts down in milliseconds. The
            # transition and native dim overlay themselves run original code.
            self.put(0x20000048,max(0,self.word(0x20000048)-dt))
        for _ in range(max(1,dt//5)):
            self.now+=5
            self.put(0x40020010,0xffff&~((0x200 if self.test_pressed else 0)|(0x100 if self.power_pressed else 0)))
            self.put(0x40020410,0xffff&~(0x8000 if self.side_pressed else 0))
            if self.now%20==0:self.call(0x0800cbd0)
            if not self.powered:return
            self.call(0x08013a94)
        if self.encoder_pending:
            # The physical boot sequence establishes an initial focus before
            # encoder interrupts arrive. Pointer interaction can leave it
            # empty in this component-level bootstrap; restore a group member.
            group=self.word(0x20000470)
            if group and not self.word(group+12):
                head=self.word(group+4)
                if head:self.call(0x0802b558,self.word(head))
        if self.simulate_idle:self.call(self.symbols['camlcd_dim_service'])
        self.call(0x080334a4)
    def flash_snapshot(self):return bytes(self.u.mem_read(0x080f4000,0x4000))
    def bank_context(self):
        root=0x200011a4;node=self.word(root+4);size=self.word(root)
        entry=next(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(self.image_bytes[0x08034040-0x08004800:0x08034044-0x08004800],0x08034040))
        init=int(entry.op_str[1:],16)
        # The injected export table immediately precedes init by 32 bytes.
        if init<0x080ed800:return 0
        callback=self.word(init-28)
        for _ in range(256):
            if not node:return 0
            if self.word(node+8)==callback:return self.word(node+12)
            node=self.word(node+size+4)
        return 0
    def save(self):self.call(0x08013a68)

if __name__=='__main__':
    m=NativeCore();m.initialize();m.frame.save(ROOT/'output/native-ui-probe.png')
    m.test_pressed=True
    for _ in range(60):m.step()
    m.frame.save(ROOT/'output/native-popup-probe.png')
