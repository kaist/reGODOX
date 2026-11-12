"""Shared ttkbootstrap palette for both English desktop apps."""
import ttkbootstrap as tb
from ttkbootstrap.style import ThemeDefinition
from ttkbootstrap.publisher import Publisher

BG='#11151c'
CARD='#1b222d'
FG='#edf2f8'
MUTED='#9aaabd'
ACCENT='#85dec0'


def setup(root):
    # Tests and screenshot capture create successive Tk interpreters. A style
    # singleton from a destroyed interpreter must never be reused.
    existing=tb.Style.instance
    if existing is not None and existing.master.tk is root.tk and existing.theme.name=='regodox':
        root.configure(bg=BG)
        return existing
    if existing is not None and existing.master.tk is not root.tk:
        tb.Style.instance=None
        Publisher.clear_subscribers()
    style=tb.Style('darkly')
    style.register_theme(ThemeDefinition('regodox',{
        'primary':'#237e65','secondary':'#9aaabd','success':'#237e65','info':'#8fbfff',
        'warning':'#f0d37a','danger':'#f08f91','light':'#d5dfea','dark':'#11151c',
        'bg':BG,'fg':FG,'selectbg':'#34485b','selectfg':FG,'border':'#303c4c',
        'inputfg':FG,'inputbg':CARD,'active':'#29394a'},'dark'))
    style.theme_use('regodox')
    root.configure(bg=BG)
    root.option_add('*Font',('Segoe UI',10))
    style.configure('TButton',font=('Segoe UI',10),padding=(15,10))
    style.configure('TLabel',font=('Segoe UI',10))
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Title.TLabel',font=('Segoe UI',28,'bold'))
    style.configure('Section.TLabel',font=('Segoe UI',11,'bold'))
    style.configure('Card.TFrame',background=CARD)
    return style
