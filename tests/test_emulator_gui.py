from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
import pytest
pytest.importorskip('unicorn')
from regodox.engine import profiles
from regodox.emulator.app import EmulatorApp

pytestmark=[pytest.mark.gui,pytest.mark.native]


def test_six_models_one_english_window(tmp_path,tk_window):
    root=tk_window;app=EmulatorApp(root,data_dir=tmp_path,auto_start=False)
    try:
        for p in profiles():
            app.selected.set(p.label);app.select_model();root.update()
            assert app.core and not app.failed,app.status['text']
            assert app.core.profile==p
            assert app.state_file.name==f'flash-{p.id}.bin'
            for key,attribute in [('space','test_pressed'),('return','side_pressed'),('p','power_pressed')]:
                app.key_down(SimpleNamespace(keysym=key));assert getattr(app.core,attribute)
                app.key_up(SimpleNamespace(keysym=key));assert not getattr(app.core,attribute)
            app.rotate(1);assert app.core.encoder_pending==1
            app.core.encoder_pending=0
            s=app.core.symbols;app.core.call(s['count_set'],2);app.core.save();app.persist()
            app.restart();assert app.core.call(s['count_get'])==2
            assert bool(app.core.call(s['camlcd_get']))==p.camlcd_default
        assert len(list(tmp_path.glob('flash-*.bin')))==6
    finally:app.close()
