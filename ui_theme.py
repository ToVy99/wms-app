"""Light/dark appearance only; never touches order data or WMS transport."""
import re
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

LIGHT_COLORS = {
    '#1e1e2e':'#f3f6fb', '#181825':'#ffffff', '#11111b':'#edf2fa',
    '#313244':'#e5ebf5', '#45475a':'#cbd5e1', '#585b70':'#94a3b8',
    '#cdd6f4':'#24324b', '#a6adc8':'#52627c', '#89b4fa':'#2563eb',
    '#f38ba8':'#be185d', '#a6e3a1':'#166534', '#f9e2af':'#854d0e',
    '#cba6f7':'#7e22ce', '#fab387':'#9a3412',
    '#202132':'#ffffff', '#393c52':'#cbd5e1', '#c4c9df':'#475569',
    '#292b3f':'#f8fafc', '#484b65':'#cbd5e1', '#363951':'#e0edff',
    '#3b3528':'#fff0c2', '#232436':'#e2e8f0', '#ffffff':'#172033',
    '#cbd0e5':'#475569', '#24483d':'#dcfce7', '#69e6b2':'#15803d',
    '#94f7d0':'#166534', '#151e34':'#ffffff', '#5c8cde':'#93b4e7',
    '#85baff':'#2563eb', '#1b2944':'#eff6ff', '#a4e7ff':'#075985',
    '#202d42':'#eaf5ff', '#3d597c':'#b6d6f1', '#535974':'#b8c6dc',
    '#6a4b13':'#ffe29a', '#fff1b5':'#713f12', '#ffc052':'#e9a116',
    '#ff9d37':'#e9a116', '#49402c':'#ffe29a',
    '#2e3c38':'#dcfce7', '#442a38':'#ffe4e6',
}

def light_css(css):
    return re.sub(r'#[0-9a-fA-F]{6}', lambda m:LIGHT_COLORS.get(m[0].lower(),m[0]),css)

def preserve_colors(widget):
    while widget is not None:
        if widget.property('preserveThemeColors'):return True
        widget=widget.parentWidget()
    return False

class ThemeController(QObject):
    def __init__(self,window,save_config):
        super().__init__(window)
        self.window=window;self.save_config=save_config;self.app=QApplication.instance()
        self.mode=window.config.get('appearance','system')
        self.system_scheme=self.app.styleHints().colorScheme()
        if self.mode not in ('system','light','dark'):self.mode='system'
        self.app.styleHints().colorSchemeChanged.connect(self.system_changed)
        self.app.aboutToQuit.connect(self.disconnect_signals)
        self._applying=False
        self._palette_light=None
        self.apply()

    @property
    def light(self):
        return self.mode=='light' or (self.mode=='system' and self.system_scheme!=Qt.ColorScheme.Dark)

    def choose(self,mode):
        if mode not in ('system','light','dark'):return
        self.mode=mode;self.window.config['appearance']=mode
        self.apply()
        if not self.save_config(self.window.config):
            self.window.lblStatusMsg.setText('Đã đổi giao diện; chưa lưu được lựa chọn cho lần mở sau.')

    def system_changed(self,scheme):
        self.system_scheme=scheme
        if self.mode=='system':self.apply()

    def disconnect_signals(self):
        for signal,slot in [(self.app.styleHints().colorSchemeChanged,self.system_changed)]:
            try:signal.disconnect(slot)
            except RuntimeError:pass

    def apply(self):
        if self._applying:return
        self._applying=True
        try:
            light=self.light
            palette=QPalette()
            for role,color in {
                QPalette.ColorRole.Window:'#f3f6fb' if light else '#1e1e2e',
                QPalette.ColorRole.Base:'#ffffff' if light else '#181825',
                QPalette.ColorRole.AlternateBase:'#edf2fa' if light else '#232436',
                QPalette.ColorRole.Text:'#24324b' if light else '#cdd6f4',
                QPalette.ColorRole.WindowText:'#24324b' if light else '#cdd6f4',
                QPalette.ColorRole.Button:'#e5ebf5' if light else '#313244',
                QPalette.ColorRole.ButtonText:'#24324b' if light else '#cdd6f4',
                QPalette.ColorRole.Highlight:'#2563eb',
                QPalette.ColorRole.HighlightedText:'#ffffff',
                QPalette.ColorRole.ToolTipBase:'#ffffff' if light else '#313244',
                QPalette.ColorRole.ToolTipText:'#24324b' if light else '#cdd6f4',
            }.items():palette.setColor(role,QColor(color))
            if self._palette_light!=light:
                self.app.setPalette(palette)
                self._palette_light=light
            roots=[self.window]+[w for w in self.app.topLevelWidgets() if w.window()!=self.window and self.window.isAncestorOf(w)]
            for root in roots:
                for w in [root]+root.findChildren(QWidget):
                    if preserve_colors(w):continue
                    if hasattr(w,'set_popup_theme'):w.set_popup_theme(light)
                    css=w.styleSheet();old=w.property('_themeLastCss')
                    if old is None or css!=old:w.setProperty('_themeDarkCss',css)
                    dark=w.property('_themeDarkCss') or ''
                    new=light_css(dark) if light else dark
                    if css!=new:w.setStyleSheet(new)
                    w.setProperty('_themeLastCss',new)
            # Charts are painted by Matplotlib instead of Qt stylesheets.
            for canvas in self.window.findChildren(QWidget):
                if hasattr(canvas,'set_light_theme'):canvas.set_light_theme(light)
        finally:self._applying=False
