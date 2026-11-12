from pathlib import Path
import pytest
import sys
import tkinter as tk
from regodox.engine import profiles

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(params=profiles(),ids=lambda p:p.id)
def profile(request):return request.param


@pytest.fixture
def original(profile):return (ROOT/'firmware/original'/profile.original_name).read_bytes()


@pytest.fixture(scope='session')
def tk_display():
    try:root=tk.Tk()
    except tk.TclError as exc:
        if sys.platform=='win32':pytest.fail('Tk initialization failed: '+str(exc))
        pytest.skip('Tk display unavailable: '+str(exc))
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def tk_window(tk_display):
    # One Tcl interpreter matches normal application lifetime and avoids
    # intermittent Windows Tcl init.tcl reads between rapid interpreter teardown.
    window=tk.Toplevel(tk_display);window.withdraw()
    yield window
    if window.winfo_exists():window.destroy()
