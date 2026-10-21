"""Pure-Python translation of WMS Productivity core.js and popup.js data arithmetic.

Behavior is regression-checked against the original JavaScript with deterministic fixtures.
This module performs no requests or writes and changes no IntraCity COT logic.
"""
from __future__ import annotations
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))
DEFAULT_TARGETS = {'Sort':270,'Check':270,'Check Station':270,'Check&Pack':60,'Pack':55}
DEFAULT_ORDER_TARGETS = {'Sort':110,'Check':110,'Pack':110}


def num(v):
    if v is None or v == '': return None
    try:
        value = float(v)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError): return None


def number(v):
    return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)


def norm(v): return v.strip().lower() if isinstance(v,str) else ''

def norm_id(v): return v.strip().upper() if isinstance(v,str) else ''


def vn_parts(now): return datetime.fromtimestamp(now, VN_TZ)


def vn_unix(y,mo,d,h=0,m=0):
    return int((datetime(y,mo,1,tzinfo=VN_TZ)+timedelta(days=d-1,hours=h,minutes=m)).timestamp())


def hour_window(now):
    d=vn_parts(now); begin=vn_unix(d.year,d.month,d.day,d.hour)
    return {'from':begin,'to':begin+3599}


def hour_windows(now):
    cur=hour_window(now)
    return {'prev':{'from':cur['from']-3600,'to':cur['from']-1},'cur':cur}


def default_task_range(now):
    d=vn_parts(now)
    return {'start':vn_unix(d.year,d.month,d.day-6),'end':vn_unix(d.year,d.month,d.day)+86399}


def shift_window(now):
    d=vn_parts(now)
    if 6 <= d.hour < 18: h=6; shift='morning'; day=d.day
    elif d.hour>=18: h=18; shift='night'; day=d.day
    else: h=18; shift='night'; day=d.day-1
    begin=vn_unix(d.year,d.month,day,h)
    return {'from':begin,'to':vn_unix(d.year,d.month,d.day,d.hour)+3599,'end':begin+12*3600-1,'shift':shift}


def station_number(id):
    match=re.search(r'(\d{5})$',id.strip() if isinstance(id,str) else '')
    return int(match[1]) if match else None


def area_of(station_id):
    val=station_number(station_id)
    return 'Check&Pack' if val is not None and val >=500 else 'Check'


def first_station(task):
    if task.get('checking_station_id'):return task['checking_station_id']
    sid=task.get('station_id') or ''
    if isinstance(sid,list):return sid[0] if sid else ''
    return sid


def station_table(path=None):
    source=Path(path or Path(__file__).resolve().parent/'productivity'/'stations.js').read_text(encoding='utf-8')
    start=source.index('{',source.index('var STATIONS'))
    end=source.index('\n};',start)+2
    return json.loads(source[start:end])


def lookup_station(sid, stations):
    key=norm_id(sid)
    m=re.fullmatch(r'(CS|PS|SS)\d{5}',key)
    if not m:return None
    return (stations.get(m[1]) or {}).get(key) or None


def hour_map(rows):
    out={}
    for row in rows or []:
        email=norm(row.get('staff_email'))
        if email and email not in out:out[email]=num(row.get('productivity'))
    return out


def hour_of(hour_map_, email): return (hour_map_ or {}).get(norm(email))


def station_vals(r): return [r.get('staffProd'),r.get('hPrev'),r.get('hCur')]


def has_any(vals):return any(number(v) for v in vals)


def fail_count(vals,target):return sum(1 for v in vals if number(v) and v<target)


def rank_below(rows, get_vals, target, tie_key):
    keep=[r for r in rows if fail_count(get_vals(r),target)>0]
    keep.sort(key=lambda r:(-fail_count(get_vals(r),target),
                             get_vals(r)[0] if number(get_vals(r)[0]) else float('inf'),
                             str(tie_key(r) or '').casefold()))
    return keep


def station_ids(stations):
    out=[]
    for s in stations or []:
        sid=norm_id(s.get('station_id'))
        if sid and sid not in out:out.append(sid)
    return out


def last_operator_by_station(tasks):
    out={}
    for t in tasks or []:
        sid=norm_id(t.get('checked_station_id') or first_station(t))
        email=norm(t.get('operator'))
        if not sid or not email:continue
        timestamp=t.get('done_time') or t.get('complete_time') or t.get('ongoing_time') or t.get('ctime') or 0
        old=out.get(sid)
        if old is None or timestamp>old['t']:
            out[sid]={'email':email,'rawEmail':t.get('operator'),'t':timestamp}
    return out


def build_station_rows(stations,people,operator_map,hours,station_names):
    people_by_email={}
    for p in people or []:
        email=norm(p.get('staff_email'))
        if email and email not in people_by_email:
            people_by_email[email]={'name':p.get('local_staff_name') or p.get('staff_name') or '',
                                    'email':p.get('staff_email'), 'prod':num(p.get('productivity')),
                                    'mh':num(p.get('man_hour'))}
    out=[];seen=set()
    for s in stations or []:
        sid=norm_id(s.get('station_id'))
        if not sid or sid in seen:continue
        seen.add(sid)
        op=operator_map.get(sid)
        info=people_by_email.get(op['email']) if op else None
        out.append({'stationId':sid,'stationName':lookup_station(sid,station_names),
                    'prod':num(s.get('productivity')) or 0,'manHour':num(s.get('man_hour')),
                    'items':num(s.get('sum_count')),
                    'operatorEmail':(info['email'] if info else op['rawEmail']) if op else None,
                    'operatorName':info['name'] if info and info['name'] else None,
                    'staffProd':info['prod'] if info else None,
                    'staffMh':info['mh'] if info else None,
                    'hPrev':hour_of(hours.get('prev'),op['email']) if op and hours else None,
                    'hCur':hour_of(hours.get('cur'),op['email']) if op and hours else None})
    return out


def filter_station_rows(rows,tab,target):
    return rank_below([r for r in rows if area_of(r['stationId'])==tab],station_vals,target,lambda r:r['stationId'])


def count_stations(rows,tab):
    eligible=[r for r in rows if area_of(r['stationId'])==tab]
    total=sum(1 for r in eligible if has_any(station_vals(r)))
    return {'total':total,'hidden':len(eligible)-total}


def group_by_operator(rows):
    by={};hidden=0
    for r in rows or []:
        if not r.get('operatorEmail') or not has_any(station_vals(r)):
            hidden+=1;continue
        key=norm(r['operatorEmail'])
        if key not in by:
            by[key]={'email':r['operatorEmail'],'name':r.get('operatorName'),
                     'staffProd':r.get('staffProd'),'staffMh':r.get('staffMh'),
                     'hPrev':r.get('hPrev'),'hCur':r.get('hCur'),'stations':[]}
        by[key]['stations'].append({'stationId':r['stationId'],'stationName':r.get('stationName'),
                                    'prod':r.get('prod'),'manHour':r.get('manHour'),'items':r.get('items')})
    persons=list(by.values())
    for p in persons:p['stations'].sort(key=lambda st:st['stationId'])
    return {'persons':persons,'hidden':hidden}


def filter_sort_persons(rows,target):
    return rank_below(rows,station_vals,target,lambda r:r.get('name') or r.get('email'))


def build_pack_station_map(tasks):
    out={};in_list=set()
    def put(email,sid,ts):
        cur=out.get(email)
        if cur is None or ts>cur['t']:out[email]={'stationId':sid,'t':ts}
    for task in tasks or []:
        sid=first_station(task);ts=task.get('start_time') or task.get('ctime') or 0
        if not sid:continue
        for member in task.get('list') or []:
            e=norm(member.get('email'))
            if e:in_list.add(e);put(e,sid,ts)
    for task in tasks or []:
        sid=first_station(task);ts=task.get('start_time') or task.get('ctime') or 0;e=norm(task.get('operator'))
        if sid and e and e not in in_list:put(e,sid,ts)
    return out


def merge_rows(items,orders,station_map,hours,station_names):
    orders_by_email={};orders_qty={}
    for row in orders or []:
        email=norm(row.get('staff_email'))
        if email and email not in orders_by_email:
            orders_by_email[email]=num(row.get('productivity'))
            exact=num(row.get('sum_count'))
            if exact is not None:orders_qty[email]=exact
    out=[];seen=set()
    for item in items or []:
        email=norm(item.get('staff_email'))
        if not email or email in seen:continue
        seen.add(email)
        station=station_map.get(email); sid=station.get('stationId') if station else None
        out.append({'name':item.get('local_staff_name') or item.get('staff_name') or item.get('staff_email'),
                    'email':item.get('staff_email'),'items':num(item.get('productivity')) or 0,
                    'orders':orders_by_email.get(email),'manHour':num(item.get('man_hour')),
                    'stationId':sid,'stationName':lookup_station(sid,station_names) if sid else None,
                    'hPrev':hour_of(hours.get('prev'),email) if hours else None,
                    'hCur':hour_of(hours.get('cur'),email) if hours else None})
        exact_item=num(item.get('sum_count'))
        if exact_item is not None:out[-1]['itemThroughput']=exact_item
        if email in orders_qty:out[-1]['orderThroughput']=orders_qty[email]
    return out


def filter_pack_rows(rows,target):
    return rank_below(rows,lambda r:[r['items'],r.get('hPrev'),r.get('hCur')],target,lambda r:r['name'])


def build_people(items):
    people={}
    for source in items or []:
        email=norm(source.get('staff_email'))
        if not email:continue
        prod=num(source.get('productivity'));mh=num(source.get('man_hour'))
        if email not in people:
            people[email]={'name':source.get('local_staff_name') or source.get('staff_name') or source.get('staff_email'),
                           'email':source.get('staff_email'),'productivity':None,'manHour':None,'items':None,
                           '_qty':0,'_hours':0,'_missing':0}
        p=people[email]
        if number(prod) and number(mh) and mh>0:
            exact=num(source.get('sum_count'))
            p['_qty']+=exact if exact is not None else prod*mh
            p['_hours']+=mh
        else:p['_missing']+=1
    result=[]
    for p in people.values():
        if p['_hours']>0 and p['_missing']==0:
            p['productivity']=p['_qty']/p['_hours'];p['manHour']=p['_hours'];p['items']=p['_qty']
        del p['_qty'],p['_hours'],p['_missing']
        result.append(p)
    return result


def filter_people(rows,target):
    return sorted((r for r in rows if number(r.get('productivity')) and r['productivity']<target),key=lambda r:r['productivity'])


def filtered_view(rows, tab, target, show_all=False, unit='item_count', ascending=False):
    is_people=tab in ('Sort','Check')
    if tab=='Pack':
        below=([r for r in rows if number(r.get('orders')) and r['orders']<target] if unit=='order_count'
               else filter_pack_rows(rows,target))
        displayed=list(rows) if show_all else below
        total=len(rows);hidden=0
    elif is_people:
        below=filter_people(rows,target)
        displayed=list(rows) if show_all else below
        total=len(rows);hidden=0
    else:
        kind='Check' if tab=='Check Station' else tab
        eligible=[r for r in rows if area_of(r['stationId'])==kind]
        below=sorted((r for r in eligible if number(r.get('prod')) and r['prod']<target),key=lambda r:r['prod']) if tab=='Check Station' else filter_station_rows(rows,kind,target)
        displayed=eligible if show_all else below
        counts=count_stations(rows,kind)
        total=len(eligible) if tab=='Check Station' else counts['total']
        hidden=0 if tab=='Check Station' else counts['hidden']
    def score(r):
        field=('orders' if unit=='order_count' else 'items') if tab=='Pack' else 'productivity' if is_people else 'prod'
        return num(r.get(field))
    displayed=sorted(displayed,key=lambda r:(score(r) is None, score(r) * (1 if ascending else -1) if score(r) is not None else 0))
    return {'rows':displayed,'below':below,'total':total,'hidden':hidden}


def summary(rows, tab, unit, below_count):
    people=tab in ('Sort','Check');pack=tab=='Pack';is_order=unit=='order_count' and (people or pack)
    src=rows if (people or pack) else [r for r in rows if area_of(r['stationId'])==('Check' if tab=='Check Station' else tab)]
    def qty_of(r):
        if pack:
            exact=num(r.get('orderThroughput' if is_order else 'itemThroughput'))
            if exact is not None:return exact
            p=num(r.get('orders' if is_order else 'items'));mh=num(r.get('manHour'))
            return p*mh if p is not None and mh is not None else None
        return num(r.get('items'))
    vals=[r for r in src if number(qty_of(r)) and number(r.get('manHour')) and r['manHour']>0]
    qty=sum(qty_of(r) for r in vals)
    mh=sum(r['manHour'] for r in vals)
    pr=[]
    for r in vals:
        val=r.get('productivity') if people else r.get('orders' if is_order else 'items') if pack else r.get('prod')
        if number(val):pr.append(val)
    return {'qty':qty,'weighted':qty/mh if mh>0 else None,'avg':sum(pr)/len(pr) if pr else None,
            'manHour':mh,'below':below_count,'unit':'Orders' if is_order else 'Items'}
