"""A shared watchdog avoids Unicorn's costly per-instruction counting hook.

Only trusted, fingerprint-verified firmware is accepted by the factory. Calls
still stop after two wall-clock seconds; an invalid call cannot freeze Tk forever.
"""
from dataclasses import dataclass
import threading
import time

_lock=threading.Lock()
_active={}
_started=False


@dataclass
class _Call:
    engine:object
    deadline:float
    expired:bool=False


def _watch():
    event=threading.Event()
    while not event.wait(0.05):
        with _lock:
            now=time.monotonic()
            for call in _active.values():
                if now>=call.deadline:
                    call.expired=True
                    call.engine.emu_stop()


def run(engine,begin,end):
    global _started
    call=_Call(engine,time.monotonic()+2.0);key=id(engine)
    with _lock:
        if not _started:
            threading.Thread(target=_watch,name='regodox-watchdog',daemon=True).start()
            _started=True
        if key in _active:raise RuntimeError('Nested emulation is unsupported')
        _active[key]=call
    try:engine.emu_start(begin,end,count=0)
    finally:
        with _lock:_active.pop(key,None)
    if call.expired:raise TimeoutError('Native firmware call exceeded the two-second execution budget')
