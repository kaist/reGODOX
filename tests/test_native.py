"""These execute real Thumb firmware and LVGL, not a UI reimplementation."""
import struct
import pytest
pytest.importorskip('unicorn')
pytest.importorskip('capstone')
from regodox import engine
from regodox.emulator.factory import create_core,camera_status

pytestmark=pytest.mark.native


def advance(m,ms):
    for _ in range(ms//20):m.step()


def core(original,flash=None):
    m=create_core(original,flash=flash,simulate_idle=False);m.initialize();return m


def tap(m,x,y):
    m.touch=(x,y,True);advance(m,120);m.touch=(x,y,False);advance(m,400)


def swipe(m,a,b):
    for y in range(a,b,15 if b>a else -15):m.touch=(184,y,True);advance(m,20)
    m.touch=(184,b,False);advance(m,500)


def test_native_splash(profile,original):
    m=core(original);m.call(profile.native['splash']);advance(m,700)
    assert m.frame.getbbox()==(0,0,368,448)
    assert len(m.frame.getcolors(200000))==4


def test_controls_banks_menu_persistence(profile,original):
    m=core(original);s=engine.recipe(profile.id)['symbols'];c=m.bank_context()
    assert c and m.call(s['count_get'])==4
    assert bool(m.call(s['camlcd_get']))==profile.camlcd_default
    exports=struct.unpack_from('<8I',m.image_bytes,0x080ed800-0x08004800)
    capture,apply=exports[2]&~1,exports[3]&~1
    for i in range(4):
        for name,value in [('groups',0),('channel',21+i),('wireless_id',10+i),
                           ('modeling_light',i&1),('sound',i&1)]:
            if name=='groups':m.u.mem_write(profile.ram[name]+1,bytes([40+5*i]))
            else:m.u.mem_write(profile.ram[name],bytes([value]))
        m.call(capture,c,i)
    m.call(apply,c,0)
    for expected in (1,2,3,0):
        m.test_pressed=True;advance(m,620);m.test_pressed=False;advance(m,140)
        assert m.word(c+16)==expected
        assert m.u.mem_read(profile.ram['groups']+1,1)[0]==40+5*expected
        assert m.u.mem_read(profile.ram['channel'],1)[0]==21+expected
        assert m.u.mem_read(profile.ram['wireless_id'],1)[0]==10+expected
        assert m.u.mem_read(profile.ram['modeling_light'],1)[0]==(expected&1)
        assert m.u.mem_read(profile.ram['sound'],1)[0]==(expected&1)
    assert m.flash_count>=4
    m.call(s['count_set'],2);advance(m,1100)
    swipe(m,420,140);d=m.word(c+60);assert m.word(d+4)
    button=m.word(d+20);x1,y1,x2,y2=struct.unpack('<4i',m.u.mem_read(button+20,16))
    tap(m,(x1+x2)//2,(y1+y2)//2);assert m.word(c+16)==1 and not m.word(d+4)
    for mode,unit in [(2,5),(3,10)]:
        m.u.mem_write(profile.ram['step'],bytes([mode]))
        assert m.call(profile.native['m_step'],40,1)==40-unit
        assert m.call(profile.native['ttl_step'],30,1)==30+unit
    swipe(m,15,361);tap(m,270,380)
    assert m.u.mem_read(profile.ram['menu'],1)[0]==2
    assert bool(m.call(s['camlcd_tile_ref'],0))==profile.camlcd_menu
    m.call(s['count_set'],3);m.save();n=core(original,m.flash_snapshot())
    assert n.call(s['count_get'])==3
    assert bool(n.call(s['camlcd_get']))==profile.camlcd_default
    assert bytes(n.u.mem_read(n.bank_context()+64,400))==bytes(m.u.mem_read(c+64,400))


def test_actual_camera_parser_and_gpio(profile,original):
    m=core(original);camera_status(m);advance(m,100)
    d=m.word(m.bank_context()+60)
    assert bool(m.word(d+40))==profile.camera_parameters
    if profile.camera_parameters:assert bytes(m.u.mem_read(d+56,3))==bytes([0x58,0x30,0x73])
    at=profile.native['gpio_read']-0x08004800
    assert m.image_bytes[at:at+20]==original[at:at+20]
