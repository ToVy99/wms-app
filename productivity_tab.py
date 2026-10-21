"""Native PySide6 Check Prod for IntraCity 3.4 Beta.

UI is implemented with the same Qt widgets as IntraCity, not Chromium/WebEngine.
The calculation routines are translated from WMS Productivity core.js and
popup.js into prod_native_core.py, with JavaScript parity fixture tests.
All WMS requests reuse the authenticated Chrome/extension bridge unchanged.
"""
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QDate, QTime, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QComboBox, QCheckBox, QLineEdit, QDateEdit, QTimeEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QFileDialog, QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QScrollArea, QSizePolicy, QTabBar)

import prod_native_core as core
import prod_native_api as api
from prod_report_view import EmployeeTable, hourly_windows, raw_totals

TABS=('Sort','Check','Check Station','Check&Pack','Pack')
PRESETS={'BAU1':'08:00–19:00','BAU2':'19:00–06:00','CP1':'07:00–18:00','CP2':'18:00–06:00'}
VN_TZ=timezone(timedelta(hours=7))


def fmt(value):return f'{value:.2f}' if core.number(value) else '—'

def whole(value):return str(round(value)) if core.number(value) else '—'


def valid_preset(value):
    match=re.fullmatch(r'([0-2]\d:[0-5]\d)[–-]([0-2]\d:[0-5]\d)',str(value).replace(' ',''))
    if not match:return None
    times=match.groups()
    if times[0]==times[1] or any(int(t[:2])>=24 for t in times):return None
    return times


def add_line(layout,label,widget):
    layout.addWidget(QLabel(label));layout.addWidget(widget)


class CheckProdTab(QWidget):
    def __init__(self, bridge, config, save_config, parent=None):
        super().__init__(parent)
        self.bridge,self.config,self.save_config=bridge,config,save_config
        prefs=config.get('prod_settings') or {}
        if not isinstance(prefs,dict):prefs={}
        self.prefs=prefs
        self.tab=prefs.get('tab','Check') if prefs.get('tab') in TABS else 'Check'
        self.mode=prefs.get('shiftMode','BAU') if prefs.get('shiftMode') in ('BAU','CP') else 'BAU'
        self.shift_number=prefs.get('shiftNumber',1) if prefs.get('shiftNumber') in (1,2) else 1
        self.unit=prefs.get('peopleUnit','item_count') if prefs.get('peopleUnit') in ('item_count','order_count') else 'item_count'
        self.presets=dict(PRESETS)
        for key,value in (prefs.get('shiftPresets') or {}).items():
            if key in self.presets and valid_preset(value):self.presets[key]='–'.join(valid_preset(value))
        self.targets={**core.DEFAULT_TARGETS,**{k:v for k,v in (prefs.get('targets') or {}).items() if k in TABS and core.number(v) and v>0}}
        self.order_targets={**core.DEFAULT_ORDER_TARGETS,**{k:v for k,v in (prefs.get('orderTargets') or {}).items() if k in ('Sort','Check','Pack') and core.number(v) and v>0}}
        self.station_names=core.station_table()
        custom=prefs.get('stationsCustom')
        if isinstance(custom,dict) and isinstance(custom.get('CS'),dict) and isinstance(custom.get('PS'),dict):
            self.station_names={k:custom.get(k,self.station_names.get(k,{})) for k in ('CS','PS','SS')}
        self.rows=[];self.cache_key=None;self.busy=False;self.pending=None;self.task=None
        self.sort_ascending=False;self._light_theme=False;self.warnings=[];self._load_key=None
        self.request_log=[];self._retry_count=0;self._last_request=None
        self._highlighted_employee=None
        self._views={};self._restoring=True;self.hour_windows=[];self.loaded_unit=self.unit
        self._build()
        self.bridge.completed.connect(self._completed)
        self.bridge.sessionChanged.connect(self._state)
        self._state(self.bridge.connected,self.bridge.session_message)
        self._restore_range()
        self._restoring=False
        self._refresh_controls()
        self._render()

    def _save(self):
        self.config['prod_settings']=self.prefs
        if not self.save_config(self.config):self.message.setText('Không lưu được cài đặt Check Prod.')

    def _build(self):
        self.setObjectName('checkProdRoot')
        # IntraCity ThemeController styles child inputs/buttons and calls set_theme()
        # for the Check Prod-specific cards and checked-state palette.
        main=QVBoxLayout(self);main.setContentsMargins(8,4,8,4);main.setSpacing(4)
        # WMS connection status is already displayed in IntraCity's shared header;
        # avoid a second status/title strip above Check Prod controls.
        mode_row=QHBoxLayout();main.addLayout(mode_row)
        self.bau=QPushButton('BAU');self.cp=QPushButton('CP')
        self.item=QPushButton('Item');self.order=QPushButton('Order')
        self.shift1=QPushButton('Ca 1');self.shift2=QPushButton('Ca 2')
        for button in (self.bau,self.cp,self.item,self.order,self.shift1,self.shift2):
            button.setCheckable(True)
            button.setFixedSize(68,28)
            button.setProperty('prodChoice',True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        mode_row.addWidget(self.bau);mode_row.addWidget(self.cp);mode_row.addSpacing(10)
        mode_row.addWidget(self.item);mode_row.addWidget(self.order)
        mode_row.addStretch();mode_row.addWidget(self.shift1);mode_row.addWidget(self.shift2)
        self.edit_shifts=QPushButton('⚙ Giờ ca');self.edit_shifts.setFixedHeight(28);mode_row.addWidget(self.edit_shifts)
        self.bau.clicked.connect(lambda:self._set_mode('BAU'))
        self.cp.clicked.connect(lambda:self._set_mode('CP'))
        self.item.clicked.connect(lambda:self._set_unit('item_count'))
        self.order.clicked.connect(lambda:self._set_unit('order_count'))
        self.shift1.clicked.connect(lambda:self._set_shift(1))
        self.shift2.clicked.connect(lambda:self._set_shift(2))
        self.edit_shifts.clicked.connect(self._edit_shifts)

        metrics=QFrame();metrics.setObjectName('prodMetrics')
        metrics_l=QGridLayout(metrics);metrics_l.setContentsMargins(0,0,0,0);metrics_l.setSpacing(6)
        self.metrics_layout=metrics_l;self.metric_cards=[];self._metric_columns=5
        self.metric_values={}
        # Native cards; icons and values are painted by Qt and follow IntraCity's theme.
        metric_defs=[('qty','TỔNG SẢN LƯỢNG','📦'),('weighted','TỔNG PROD','▥'),
                     ('avg','PROD TRUNG BÌNH','◷'),('manHour','GIỜ CÔNG','⏱'),
                     ('below','DƯỚI TARGET','⚠')]
        for i,(key,title,glyph) in enumerate(metric_defs):
            cell=QFrame();cell.setObjectName('prodMetricCard');cell.setFixedHeight(66)
            inner=QHBoxLayout(cell);inner.setContentsMargins(8,5,8,5);inner.setSpacing(7)
            symbol=QLabel(glyph);symbol.setObjectName('prodMetricIcon');symbol.setProperty('tone',key)
            symbol.setAlignment(Qt.AlignmentFlag.AlignCenter);symbol.setFixedSize(36,36)
            symbol.setFont(QFont('Segoe UI Symbol',16))
            inner.addWidget(symbol)
            details=QVBoxLayout();details.setSpacing(1)
            small=QLabel(title);small.setObjectName('prodMetricLabel');details.addWidget(small)
            big=QLabel('—');big.setObjectName('prodMetricValue');details.addWidget(big)
            inner.addLayout(details,1)
            self.metric_values[key]=big
            self.metric_cards.append(cell)
            metrics_l.addWidget(cell,i//5,i%5)
        main.addWidget(metrics)

        # Keep the five work tabs stable; Target actions have their own line so
        # resizing / choosing a tab cannot hide one of the neighbouring tabs.
        work_row=QHBoxLayout();main.addLayout(work_row)
        work_row.addWidget(QLabel('KHU VỰC LÀM VIỆC'))
        self.tab_select=QTabBar();self.tab_select.setObjectName('prodWorkTabs')
        self.tab_select.setExpanding(False)
        self.tab_select.setUsesScrollButtons(False)
        self.tab_select.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
        for name in TABS:self.tab_select.addTab(name)
        self.tab_select.setStyleSheet('QTabBar#prodWorkTabs::tab {min-width:84px; max-width:84px; padding:4px 5px;}')
        work_row.addWidget(self.tab_select)
        work_row.addStretch(1)
        self.tab_select.currentChanged.connect(self._tab_changed)

        target_row=QHBoxLayout();main.addLayout(target_row)
        target_row.addWidget(QLabel('Target Prod'))
        self.target=QLineEdit();self.target.setFixedWidth(68);self.target.setFixedHeight(28)
        self.target.setToolTip('Target tính theo đơn vị Item hoặc Order đang chọn; không đổi công thức Prod.')
        target_row.addWidget(self.target)
        self.save_target=QPushButton('Lưu Target');self.save_target.setFixedHeight(28);self.save_target.clicked.connect(self._save_target)
        target_row.addWidget(self.save_target)
        target_row.addStretch(1)
        self.start=QPushButton('↻ Tải dữ liệu');self.start.setFixedHeight(30);self.start.clicked.connect(self._start)
        self.start.setObjectName('prodPrimaryAction')
        target_row.addWidget(self.start)

        range_row=QHBoxLayout();main.addLayout(range_row)
        range_row.addWidget(QLabel('KHUNG GIỜ BÁO CÁO'))
        self.date=QDateEdit();self.date.setCalendarPopup(True);self.date.setDisplayFormat('dd/MM/yyyy')
        self.date.setDate(QDate.currentDate());self.date.setFixedHeight(28);range_row.addWidget(self.date)
        range_row.addWidget(QLabel('Từ'))
        self.from_time=QLineEdit();self.from_time.setPlaceholderText('HH:mm');self.from_time.setFixedWidth(80)
        range_row.addWidget(self.from_time)
        range_row.addWidget(QLabel('Đến'))
        self.to_time=QLineEdit();self.to_time.setPlaceholderText('HH:mm');self.to_time.setFixedWidth(80)
        range_row.addWidget(self.to_time)
        range_row.addWidget(QLabel('Nhập tay · gồm cả phút kết thúc'))
        range_row.addStretch()
        self.date.dateChanged.connect(self._persist_interval)
        self.from_time.textChanged.connect(self._persist_interval)
        self.to_time.textChanged.connect(self._persist_interval)

        filter_row=QHBoxLayout();main.addLayout(filter_row)
        self.show_all=QCheckBox('Hiện tất cả (kể cả đạt Target)');self.show_all.toggled.connect(self._render)
        filter_row.addWidget(self.show_all);filter_row.addStretch()
        self.direction=QPushButton('↓ Cao → Thấp');self.direction.setFixedHeight(28);self.direction.clicked.connect(self._flip)
        filter_row.addWidget(self.direction)
        self.export=QPushButton('Xuất Excel');self.export.setFixedHeight(28);self.export.clicked.connect(self._export)
        filter_row.addWidget(self.export)
        self.mapping=QPushButton('Station mapping');self.mapping.setFixedHeight(28);self.mapping.clicked.connect(self._mapping)
        filter_row.addWidget(self.mapping)

        self.message=QLabel();self.message.setWordWrap(True);self.message.setObjectName('prodMessage')
        main.addWidget(self.message)
        count_row=QHBoxLayout();main.addLayout(count_row)
        self.count=QLabel();count_row.addWidget(self.count);count_row.addStretch()
        self.clear_highlight=QPushButton('Bỏ tô sáng')
        self.clear_highlight.setEnabled(False)
        self.clear_highlight.clicked.connect(self._clear_employee_highlight)
        count_row.addWidget(self.clear_highlight)
        self.table=EmployeeTable();self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(self._employee_clicked)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        main.addWidget(self.table,1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'metric_cards'):self._reflow_metrics()

    def _reflow_metrics(self):
        cols=5 if self.width()>=1100 else 3 if self.width()>=700 else 2
        if cols==self._metric_columns:return
        for card in self.metric_cards:self.metrics_layout.removeWidget(card)
        for i,card in enumerate(self.metric_cards):self.metrics_layout.addWidget(card,i//cols,i%cols)
        self._metric_columns=cols

    def set_theme(self, light):
        # Presentation only: formulas, request payloads and data are untouched.
        self._light_theme=bool(light)
        bg='#f3f6fb' if light else '#1e1e2e'
        card='#ffffff' if light else '#313244'
        border='#dce5f2' if light else '#494b69'
        fg='#182a49' if light else '#e6eafa'
        secondary='#52627c' if light else '#b4c0e5'
        button='#e5ebf5' if light else '#313244'
        active='#2563eb' if light else '#89b4fa'
        active_text='#ffffff' if light else '#11111b'
        hover='#dbe7fb' if light else '#45475a'
        style=f'''
        QWidget#checkProdRoot {{background:{bg}; color:{fg};}}
        QFrame#prodMetrics {{background:transparent; border:none;}}
        QFrame#prodMetricCard {{background:{card}; border:1px solid {border}; border-radius:11px;}}
        QLabel#prodMetricLabel {{color:{secondary}; font-size:10px; font-weight:600;}}
        QLabel#prodMetricValue {{color:{fg}; font-size:17px; font-weight:700;}}
        QLabel#prodMetricIcon {{border-radius:9px; font-size:16px; font-weight:700;}}
        QLabel#prodMetricIcon[tone="qty"] {{background:{'#e0edff' if light else '#254471'};color:{'#1467c0' if light else '#b7d6ff'};}}
        QLabel#prodMetricIcon[tone="weighted"] {{background:{'#def5eb' if light else '#24483d'};color:{'#127a53' if light else '#a6e3a1'};}}
        QLabel#prodMetricIcon[tone="avg"] {{background:{'#eee3ff' if light else '#3b3155'};color:{'#8040c5' if light else '#cba6f7'};}}
        QLabel#prodMetricIcon[tone="manHour"] {{background:{'#fff0df' if light else '#4a3828'};color:{'#be6716' if light else '#fab387'};}}
        QLabel#prodMetricIcon[tone="below"] {{background:{'#ffe9ec' if light else '#492b35'};color:{'#ce3145' if light else '#f4a7b9'};}}
        QPushButton[prodChoice="true"] {{background:{button};color:{fg};border:1px solid {border};border-radius:6px;padding:5px 8px;font-weight:600;}}
        QPushButton[prodChoice="true"]:hover {{background:{hover};}}
        QPushButton[prodChoice="true"]:checked {{background:{active};color:{active_text};border-color:{active};}}
        QPushButton[prodChoice="true"]:disabled {{color:{secondary};}}
        QTabBar#prodWorkTabs::tab {{background:{button};color:{fg};border:1px solid {border};border-radius:5px;padding:4px 5px;min-width:84px;max-width:84px;}}
        QTabBar#prodWorkTabs::tab:selected {{background:{active};color:{active_text};font-weight:700;border-color:{active};}}
        QTabBar#prodWorkTabs::tab:hover:!selected {{background:{hover};}}
        QPushButton#prodPrimaryAction {{background:{active};color:{active_text};border:1px solid {active};font-weight:700;}}
        '''
        style+=f"""
        QTableView {{background:{card};alternate-background-color:{bg};color:{fg};
                    gridline-color:{border};border:1px solid {border};selection-background-color:{hover};selection-color:{fg};}}
        QTableView::item {{padding:6px;border-bottom:1px solid {border};}}
        QHeaderView::section {{background:{button};color:{secondary};padding:7px;border:0;border-bottom:1px solid {border};font-weight:600;}}
        """
        self.setStyleSheet(style)
        self._apply_employee_highlight()

    def _state(self,connected,message):
        # Keep connection metadata for diagnostics without duplicating the
        # shared header indicator. No change to any bridge or API behavior.
        self._wms_connected=bool(connected)
        self._wms_connection_message=str(message)

    def _restore_range(self):
        self.tab_select.blockSignals(True)
        self.tab_select.setCurrentIndex(TABS.index(self.tab))
        self.tab_select.blockSignals(False)
        self._restore_view(self.tab)

    def _draft(self):
        return {'date':self.date.date().toString('yyyy-MM-dd'),
                'from':self.from_time.text(),'to':self.to_time.text(),
                'unit':self.unit,'mode':self.mode,'shift':self.shift_number}

    def _persist_interval(self,*_):
        if self._restoring:return
        self.prefs.setdefault('tabIntervals',{})[self.tab]=self._draft()
        self._save()
        # Editing the next query never clears the last successful snapshot.

    def _view_key(self):
        return (self.tab,self.unit,self.date.date().toString('yyyy-MM-dd'),
                self.from_time.text(),self.to_time.text())

    def _capture_view(self):
        self._views[self.tab]={'draft':self._draft(),'rows':self.rows,'cache_key':self.cache_key,
            'loaded_unit':self.loaded_unit,'hours':self.hour_windows,
            'show_all':self.show_all.isChecked(),'ascending':self.sort_ascending,
            'target_text':self.target.text(),
            'highlight':self._highlighted_employee,'message':self.message.text(),
            'scroll':(self.table.horizontalScrollBar().value(),self.table.verticalScrollBar().value()),
            'widths':[self.table.columnWidth(c) for c in range(self.table.columnCount())]}

    def _restore_view(self,tab):
        self._restoring=True
        state=self._views.get(tab,{})
        draft=state.get('draft',self.prefs.get('tabIntervals',{}).get(tab,{}))
        self.unit=draft.get('unit','item_count');self.mode=draft.get('mode','BAU');self.shift_number=draft.get('shift',1)
        self.date.setDate(QDate.fromString(draft.get('date',datetime.now(VN_TZ).strftime('%Y-%m-%d')),'yyyy-MM-dd'))
        self.from_time.setText(draft.get('from',''));self.to_time.setText(draft.get('to',''))
        self.rows=state.get('rows',[]);self.cache_key=state.get('cache_key')
        self.loaded_unit=state.get('loaded_unit',self.unit);self.hour_windows=state.get('hours',[])
        self.sort_ascending=state.get('ascending',False)
        self.direction.setText('↑ Thấp → Cao' if self.sort_ascending else '↓ Cao → Thấp')
        self.show_all.blockSignals(True);self.show_all.setChecked(state.get('show_all',False));self.show_all.blockSignals(False)
        self._highlighted_employee=state.get('highlight');self.message.setText(state.get('message',''))
        self._refresh_controls();self._render()
        if 'target_text' in state:self.target.setText(state['target_text'])
        for c,width in enumerate(state.get('widths',[])):
            if c<self.table.columnCount():self.table.setColumnWidth(c,width)
        self.table.sync_frozen()
        h,v=state.get('scroll',(0,0))
        self.table.horizontalScrollBar().setValue(h);self.table.verticalScrollBar().setValue(v)
        self._restoring=False

    def _save_target(self):
        try:value=float(self.target.text())
        except ValueError:value=0
        if not math.isfinite(value) or value<=0:
            QMessageBox.warning(self,'Target','Target phải là số lớn hơn 0.');return
        selected=self.order_targets if self.unit=='order_count' and self.tab in ('Sort','Check','Pack') else self.targets
        selected[self.tab]=value
        self.prefs['targets']=self.targets;self.prefs['orderTargets']=self.order_targets;self._save();self._render()

    def _active_target(self):
        if self.unit=='order_count' and self.tab in ('Sort','Check','Pack'):
            return self.order_targets[self.tab]
        return self.targets[self.tab]

    def _refresh_controls(self):
        for b,active in [(self.bau,self.mode=='BAU'),(self.cp,self.mode=='CP'),
                         (self.item,self.unit=='item_count'),(self.order,self.unit=='order_count'),
                         (self.shift1,self.shift_number==1),(self.shift2,self.shift_number==2)]:
            b.setChecked(active)
        enabled=self.tab in ('Sort','Check','Pack')
        for b in (self.item,self.order):b.setEnabled(enabled)
        self.target.setText(str(self._active_target()))
        self.date.setEnabled(True)
        self.from_time.setEnabled(True)
        self.to_time.setEnabled(True)

    def _set_mode(self,value):
        if self.busy:return
        self.mode=value;self.prefs['shiftMode']=value;self._save();self._refresh_controls();self._persist_interval()

    def _set_shift(self,value):
        if self.busy:return
        self.shift_number=value;self.prefs['shiftNumber']=value;self._save();self._refresh_controls();self._persist_interval()

    def _set_unit(self,value):
        if self.busy or value==self.unit:return
        self.unit=value;self._persist_interval();self._refresh_controls()

    def _tab_changed(self,index):
        if self._restoring or index<0 or index>=len(TABS) or TABS[index]==self.tab:return
        self._capture_view()
        self.tab=TABS[index];self.prefs['tab']=self.tab;self._save()
        self._restore_view(self.tab)

    def _edit_shifts(self):
        dialog=QDialog(self);dialog.setWindowTitle('Điều chỉnh khung giờ BAU / CP')
        form=QFormLayout(dialog)
        fields={}
        for key in PRESETS:
            w=QLineEdit(self.presets[key]);fields[key]=w;form.addRow(key,w)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        form.addWidget(buttons);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        if not dialog.exec():return
        next_presets={}
        for key,w in fields.items():
            val=valid_preset(w.text())
            if not val:
                QMessageBox.warning(self,'Khung giờ','Cần nhập HH:mm–HH:mm, giờ bắt đầu khác giờ kết thúc.');return
            next_presets[key]='–'.join(val)
        self.presets=next_presets;self.prefs['shiftPresets']=self.presets;self._save();self._refresh_controls();self._persist_interval()

    def _interval(self,now):
        day=self.date.date().toString('yyyy-MM-dd')
        start=self.from_time.text().strip();end=self.to_time.text().strip()
        if any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',t) for t in (start,end)):
            raise ValueError('Nhập giờ bắt đầu và kết thúc theo HH:mm, ví dụ 07:00–18:59.')
        from_ts=int(datetime.fromisoformat(day+'T'+start+':00').replace(tzinfo=VN_TZ).timestamp())
        to_ts=int(datetime.fromisoformat(day+'T'+end+':59').replace(tzinfo=VN_TZ).timestamp())
        if end<start:to_ts+=86400
        if from_ts>now:raise ValueError('Giờ bắt đầu không được ở tương lai.')
        if to_ts>now:raise ValueError('Giờ kết thúc không được ở tương lai; hãy nhập khung giờ đã hoàn tất.')
        return {'from':from_ts,'to':to_ts}

    def _load(self, tab, unit, now, email):
        # Cache only within this explicit load. A failed refresh cannot replace a snapshot.
        interval=self._interval(now)
        self._query_cache={}
        rows=yield from self._load_base(tab,unit,now,email)
        station=tab in ('Check Station','Check&Pack')
        task_type=43 if tab=='Sort' else 42 if tab=='Pack' else 41
        dim='station' if station else 'individual'
        windows=hourly_windows(interval)
        for window in [interval]+windows:
            totals={}
            for column in ('item_count','order_count'):
                raw=yield from self._fetch_productivity(window['from'],window['to'],task_type,column,dim,email)
                totals[column]=raw_totals(raw,station)
            for row in rows:
                key=core.norm_id(row.get('stationId')) if station else core.norm(row.get('email'))
                exact={column:totals[column].get(key,{}) for column in totals}
                if window is interval:row['apiTotals']=exact
                else:row.setdefault('hourly',[]).append(exact)
        self._result_windows=windows
        return rows

    def _fetch_productivity(self,start,end,task_type,column='item_count',dim='individual',email=''):
        key=(start,end,task_type,column,dim,email)
        cache=getattr(self,'_query_cache',None)
        if cache is not None and key in cache:return cache[key]
        rows=yield from api.fetch_productivity(start,end,task_type,column,dim,email)
        if cache is not None:cache[key]=rows
        return rows

    def _load_base(self, tab, unit, now, email):
        self.warnings=[]
        interval=self._interval(now)
        if tab in ('Sort','Check'):
            items=yield from self._fetch_productivity(interval['from'],interval['to'],
                    43 if tab=='Sort' else 41,unit,'individual',email)
            return core.build_people(items)
        hw=core.hour_windows(interval['to'])
        if tab=='Pack':
            items=yield from self._fetch_productivity(interval['from'],interval['to'],42,'item_count','individual',email)
            orders=yield from self._fetch_productivity(interval['from'],interval['to'],42,'order_count','individual',email)
            try:tasks=yield from api.fetch_pack_tasks()
            except api.WMSRequestError as exc:tasks=[];self.warnings.append(str(exc)+' · thiếu Station')
            prev=yield from self._soft_hours(hw['prev'],42,email)
            cur=yield from self._soft_hours(hw['cur'],42,email,cache=items if hw['cur']['from']==interval['from'] and hw['cur']['to']==interval['to'] else None)
            return core.merge_rows(items,orders,core.build_pack_station_map(tasks),{'prev':core.hour_map(prev),'cur':core.hour_map(cur)},self.station_names)
        base=interval
        stations=yield from self._fetch_productivity(base['from'],base['to'],41,'item_count','station',email)
        if not stations:return []
        try:people=yield from self._fetch_productivity(base['from'],base['to'],41,'item_count','individual',email)
        except api.WMSRequestError as exc:people=[];self.warnings.append('Không có dữ liệu nhân viên: '+str(exc))
        try:
            if now-interval['to']<120:
                tasks=yield from api.fetch_checked_recent(now,core.station_ids(stations))
            else:
                history=yield from api.fetch_completed_range(interval['from'],interval['to'])
                tasks={'rows':history['rows'],'partial':history['partial'],'complete':not bool(history['partial'])}
        except api.WMSRequestError as exc:tasks={'rows':[],'partial':str(exc),'complete':False}
        if tasks.get('partial') and not tasks.get('complete'):self.warnings.append('Thiếu Task gần đây: '+tasks['partial'])
        prev=yield from self._soft_hours(hw['prev'],41,email)
        cur=yield from self._soft_hours(hw['cur'],41,email,cache=people if hw['cur']['from']==base['from'] and hw['cur']['to']==base['to'] else None)
        return core.build_station_rows(stations,people,core.last_operator_by_station(tasks['rows']),
                                      {'prev':core.hour_map(prev),'cur':core.hour_map(cur)},self.station_names)

    def _soft_hours(self,window,task_type,email,cache=None):
        if cache is not None:return cache
        try:return (yield from self._fetch_productivity(window['from'],window['to'],task_type,'item_count','individual',email))
        except api.WMSRequestError as exc:
            self.warnings.append('Thiếu Prod theo giờ: '+str(exc));return []

    def _start(self):
        if self.busy:return
        if not self.bridge.connected:
            QMessageBox.warning(self,'Chưa kết nối','Hãy đăng nhập WMS qua Chrome trước khi tải dữ liệu.');return
        try:
            target=float(self.target.text())
            if not math.isfinite(target) or target<=0:raise ValueError('Target phải lớn hơn 0.')
            self._interval(int(time.time()))
        except (ValueError,TypeError) as exc:QMessageBox.warning(self,'Dữ liệu không hợp lệ',str(exc));return
        self._save_target()
        self.busy=True;self.start.setEnabled(False);self.start.setText('Đang tải…')
        self.message.setText('Đang tải dữ liệu từ WMS…')
        self._load_key=self._view_key();self._load_tab=self.tab;self._load_unit=self.unit;self._result_windows=[]
        self._capture_view()
        self.task=self._load(self.tab,self.unit,int(time.time()),self.prefs.get('loginEmail','').strip())
        self._advance(None,first=True)

    def _advance(self,response,first=False):
        if not self.task:return
        try:
            msg=next(self.task) if first else self.task.send(response)
        except StopIteration as stop:
            self._capture_view()
            state=self._views[self._load_tab]
            state.update(rows=stop.value or [],cache_key=self._load_key,loaded_unit=self._load_unit,
                         hours=self._result_windows,message=' '.join(self.warnings) if self.warnings else 'Đã tải dữ liệu.')
            self._finish_load();self._restore_view(self.tab);return
        except Exception as exc:
            self._capture_view()
            state=self._views[self._load_tab]
            # Do not expose server response text, which can contain session details.
            state['message']='Không tải được dữ liệu. Giữ nguyên lần tải thành công trước; hãy thử lại.'
            self._finish_load();self._restore_view(self.tab);return
        self._last_request=msg;self._retry_count=0
        self._send_request(msg)

    def _finish_load(self):
        self.task=None;self.pending=None;self.busy=False;self._query_cache={}
        self.start.setEnabled(True);self.start.setText('↻ Tải dữ liệu')

    def _send_request(self, msg):
        if not self.task:return
        self.pending='prod-native-'+uuid4().hex
        self.bridge.request(self.pending,json.dumps(msg,ensure_ascii=False))

    def _completed(self,request_id,raw):
        if request_id!=self.pending:return
        self.pending=None
        try:reply=json.loads(raw)
        except (ValueError,TypeError):reply={'success':False,'error':'Phản hồi WMS không hợp lệ.'}
        if not isinstance(reply,dict):reply={'success':False,'error':'Phản hồi WMS không hợp lệ.'}
        error=str(reply.get('error','')) if isinstance(reply,dict) else ''
        if not reply.get('success') and ('HTTP 429' in error or 'HTTP 503' in error) and self._retry_count<4:
            delays=(800,1600,3200,6400)
            delay=delays[self._retry_count];self._retry_count+=1
            message=f'WMS giới hạn yêu cầu, thử lại lần {self._retry_count}/4 sau {delay/1000:g}s…'
            self._views[self._load_tab]['message']=message
            if self.tab==self._load_tab:self.message.setText(message)
            QTimer.singleShot(delay,lambda:self._send_request(self._last_request))
            return
        QTimer.singleShot(0,lambda:self._advance(reply))

    def _flip(self):
        self.sort_ascending=not self.sort_ascending
        self.direction.setText('↑ Thấp → Cao' if self.sort_ascending else '↓ Cao → Thấp')
        self._render()

    def _employee_clicked(self,row,col):
        name_col=1
        if col!=name_col:return
        item=self.table.item(row,col)
        key=item.data(Qt.ItemDataRole.UserRole) if item else None
        if not key:return
        self._highlighted_employee=None if key==self._highlighted_employee else key
        self.table.clearSelection()
        self._apply_employee_highlight()

    def _clear_employee_highlight(self):
        self._highlighted_employee=None
        self.table.clearSelection()
        self._apply_employee_highlight()

    def _apply_employee_highlight(self):
        # Only decorate table items; keep source rows, totals and export values intact.
        bg=QColor('#fff0ac' if self._light_theme else '#66521c')
        fg=QColor('#302400' if self._light_theme else '#fff3bb')
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item=self.table.item(row,col)
                if item is None:continue
                active=bool(self._highlighted_employee and
                            item.data(Qt.ItemDataRole.UserRole)==self._highlighted_employee)
                item.setData(Qt.ItemDataRole.BackgroundRole,bg if active else None)
                item.setData(Qt.ItemDataRole.ForegroundRole,fg if active else None)
                font=item.font();font.setBold(active);item.setFont(font)
        self.clear_highlight.setEnabled(self._highlighted_employee is not None)

    def _employee_key(self,row):
        people=self.tab in ('Sort','Check','Pack')
        email=str(row.get('email' if people else 'operatorEmail') or '').strip().casefold()
        if email:return 'email:'+email
        name=str(row.get('name' if people else 'operatorName') or '').strip().casefold()
        return 'name:'+name if name and name not in ('—','-') else None

    def _render(self,*_):
        current=self.cache_key is not None
        if not current:
            self._display_empty()
            return
        unit=self.loaded_unit
        target=(self.order_targets if unit=='order_count' and self.tab in ('Sort','Check','Pack') else self.targets)[self.tab]
        view=core.filtered_view(self.rows,self.tab,target,self.show_all.isChecked(),unit,self.sort_ascending)
        metrics=core.summary(self.rows,self.tab,unit,len(view['below']))
        eligible=self.rows if self.tab in ('Sort','Check','Pack') else [r for r in self.rows if core.area_of(r['stationId'])==('Check' if self.tab=='Check Station' else self.tab)]
        if any('apiTotals' in r for r in eligible):
            column=unit if self.tab in ('Sort','Check','Pack') else 'item_count'
            quantities=[r.get('apiTotals',{}).get(column,{}).get('qty') for r in eligible]
            metrics['qty']=sum(quantities) if all(core.number(q) for q in quantities) else None
        for key,value in metrics.items():
            if key in self.metric_values:self.metric_values[key].setText(whole(value) if key in ('qty','below') else fmt(value))
        self.count.setText(f"{len(view['below'])} dưới Target trong tổng {view['total']} · {self.tab}"+
                           (f" · {view['hidden']} Station chưa xác định" if view['hidden'] else '')+
                           f' · Đã tải: {self.cache_key[2]} {self.cache_key[3]}–{self.cache_key[4]} · '+('Order' if unit=='order_count' else 'Item'))
        people=self.tab in ('Sort','Check','Pack')
        headers=['STT','Nhân viên','Item','Order','Giờ công']
        if self.tab in ('Sort','Check'):headers+=['Prod/h','Target']
        elif self.tab=='Pack':headers+=['Prod (Item)','Prod (Order)','Prod H-1','Prod H','Station ID','Tên Station']
        else:headers+=['Station ID','Tên Station','Prod Station','Prod nhân viên','Prod H-1','Prod H']
        for window in self.hour_windows:
            headers += [window['label']+'\n'+label for label in ('Item','Order','Giờ công')]
        previous=[self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
        scroll=(self.table.horizontalScrollBar().value(),self.table.verticalScrollBar().value())
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setColumnCount(len(headers));self.table.setHorizontalHeaderLabels(headers)
            if not people:
                for col in [2,3,4]+list(range(11,len(headers))):
                    self.table.horizontalHeaderItem(col).setToolTip('Số liệu trực tiếp theo Station; nhân viên là người thao tác được ánh xạ từ Task.')
            self.table.setRowCount(len(view['rows']))
            for row,r in enumerate(view['rows']):
                employee=self._employee_key(r)
                name=r.get('name' if people else 'operatorName') or 'Chưa xác định'
                email=r.get('email' if people else 'operatorEmail') or '—'
                totals=r.get('apiTotals',{})
                values=[str(row+1),name+'\n'+email,whole(totals.get('item_count',{}).get('qty')),
                        whole(totals.get('order_count',{}).get('qty')),
                        fmt(totals.get(unit if people else 'item_count',{}).get('hours')) if 'apiTotals' in r else fmt(r.get('manHour'))]
                if self.tab in ('Sort','Check'):values += [fmt(r.get('productivity')),fmt(target)]
                elif self.tab=='Pack':values += [fmt(r.get(k)) for k in ('items','orders','hPrev','hCur')]+[r.get('stationId'),r.get('stationName')]
                else:values += [r.get('stationId'),r.get('stationName')]+[fmt(r.get(k)) for k in ('prod','staffProd','hPrev','hCur')]
                for exact in r.get('hourly',[]):
                    values += [whole(exact.get('item_count',{}).get('qty')),whole(exact.get('order_count',{}).get('qty')),
                               fmt(exact.get('item_count',{}).get('hours'))]
                values += ['—'] * (len(headers)-len(values))
                for col,value in enumerate(values):
                    item=QTableWidgetItem(str(value) if value is not None else '—')
                    item.setData(Qt.ItemDataRole.UserRole,employee)
                    if col==1:
                        item.setToolTip(name+'\n'+email+'\nBấm để tô sáng nhân viên.')
                    else:item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row,col,item)
            if previous!=headers:
                for col in range(len(headers)):self.table.setColumnWidth(col,54 if col==0 else 250 if col==1 else 110)
            self.table.sync_frozen();self._apply_employee_highlight()
            self.table.horizontalScrollBar().setValue(scroll[0]);self.table.verticalScrollBar().setValue(scroll[1])
        finally:self.table.setUpdatesEnabled(True)

    def _display_empty(self):
        self.table.setRowCount(0)
        self._clear_employee_highlight()
        for value in self.metric_values.values():value.setText('—')
        self.count.setText('Bấm Tải dữ liệu để xem '+self.tab+' · '+('Order' if self.unit=='order_count' else 'Item'))

    def _export(self):
        if self.table.rowCount()==0:
            QMessageBox.information(self,'Xuất Excel','Chưa có danh sách để xuất.');return
        path,_=QFileDialog.getSaveFileName(self,'Xuất Check Prod','Check_Prod_IntraCity_3.4.xlsx','Excel (*.xlsx)')
        if not path:return
        if not path.lower().endswith('.xlsx'):path+='.xlsx'
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='Check Prod'
        ws.append([self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())])
        for i in range(self.table.rowCount()):
            ws.append([self.table.item(i,j).text() if self.table.item(i,j) else '' for j in range(self.table.columnCount())])
        ws.freeze_panes='C2';wb.save(path)

    def _mapping(self):
        choice=QMessageBox(self)
        choice.setWindowTitle('Station mapping')
        choice.setText('Chọn nguồn tên Station:')
        load=choice.addButton('Tải Excel',QMessageBox.ButtonRole.AcceptRole)
        reset=choice.addButton('Dùng bảng mặc định',QMessageBox.ButtonRole.ResetRole)
        choice.addButton('Hủy',QMessageBox.ButtonRole.RejectRole)
        choice.exec()
        if choice.clickedButton() is reset:
            self.station_names=core.station_table()
            self.prefs.pop('stationsCustom',None)
            self._save();self.message.setText('Đã khôi phục Station mapping mặc định.')
            self._render();return
        if choice.clickedButton() is not load:return
        file,_=QFileDialog.getOpenFileName(self,'Chọn Station mapping','','Excel (*.xlsx)')
        if not file:return
        from openpyxl import load_workbook
        try:
            book=load_workbook(file,read_only=True,data_only=True)
            rows=book.worksheets[0].iter_rows(values_only=True)
            table={'CS':{},'PS':{},'SS':{}}
            for row in rows:
                sid=str(row[0]).strip().upper() if len(row)>0 and row[0] is not None else ''
                name=str(row[1]).strip() if len(row)>1 and row[1] is not None else ''
                prefix=sid[:2]
                if re.fullmatch(r'(CS|PS|SS)\d{5}',sid) and name and sid not in table[prefix]:table[prefix][sid]=name
            book.close()
            if not any(table[k] for k in table):raise ValueError('Không có Station hợp lệ trong hai cột A/B.')
        except Exception as exc:
            QMessageBox.warning(self,'Station mapping','Không đọc được file: '+str(exc));return
        self.station_names=table
        self.prefs['stationsCustom']={**table,'fileName':Path(file).name,
                     'cs':len(table['CS']),'ps':len(table['PS']),'ss':len(table['SS'])}
        self._save();self.message.setText('Đã cập nhật Station mapping: '+Path(file).name)
        self._render()
