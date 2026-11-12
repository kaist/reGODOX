"""The fast path must retain a real stop mechanism and identical native output."""
import hashlib
import pytest
pytest.importorskip('unicorn')
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from regodox.emulator.execution import run
from regodox.emulator.factory import create_core

pytestmark=pytest.mark.native


def test_watchdog_stops_nonreturning_thumb_code():
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0x1000,4096)
    u.mem_write(0x1000,b'\xfe\xe7') # b .
    with pytest.raises(TimeoutError,match='execution budget'):run(u,0x1001,0x2000)
    # Expired calls are removed, so a subsequent valid call still runs.
    u.mem_write(0x1010,b'\x00\xbf');run(u,0x1011,0x1012)


def test_counted_and_fast_framebuffers_match(original):
    hashes=[]
    for fast in (False,True):
        core=create_core(original,fast=fast,simulate_idle=False);core.initialize()
        core.test_pressed=True
        for _ in range(32):core.step()
        core.test_pressed=False
        for _ in range(10):core.step()
        hashes.append(hashlib.sha256(core.frame.tobytes()).hexdigest())
    assert hashes[0]==hashes[1]
