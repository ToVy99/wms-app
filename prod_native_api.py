"""Generator-based WMS data access for the native Check Prod tab.

Requests are passed to the existing authenticated Chrome/extension bridge. No
separate Chromium engine, cookie access, or WMS authentication is introduced.
The pagination and lookup windows mirror productivity/api.js.
"""
import math
from urllib.parse import urlencode

BASE='https://wms.ssc.shopee.vn'
PROD_URL=BASE+'/mgmt/api/wms_pc/forward_wms_be/api/v2/openapi/mgmt/workspace/pc/data_wms__warehouse_operation_whs__outbound_productivity_info_ri'
CHECK_URL=BASE+'/api/v2/apps/process/taskcenter/checkingtask/search_checking_task'
SORT_URL=BASE+'/api/v2/apps/process/taskcenter/sortingtask/search_sorting_task'
PACK_URL=BASE+'/api/v2/apps/process/outbound/packing/search_packing_task'
PAGE=20;BIG_PAGE=200;MAX_PAGES=150;MAX_OFFSET=2000;MAX_SORT_PAGES=10

class WMSRequestError(RuntimeError):pass


def _good(reply):
    if not isinstance(reply,dict) or not reply.get('success'):
        raise WMSRequestError((reply or {}).get('error','WMS không trả dữ liệu hợp lệ.'))
    data=reply.get('data')
    if not isinstance(data,dict):raise WMSRequestError('Phản hồi WMS thiếu data.')
    return data


def get(url):
    data=_good((yield {'type':'WMS_GET','url':url}))
    return data


def post(url,body):
    data=_good((yield {'type':'WMS_POST','url':url,'body':body}))
    return data


def fetch_productivity(from_time,to_time,task_type,column='item_count',dim='individual',email=''):
    body={'from_time':int(from_time),'to_time':int(to_time),'task_type':task_type,
          'dim_type':dim,'query_column':column,'order_by_column_key':'','order_type':'desc',
          'staff_email':'','time_interval':3600,'pageno':1,'count':PAGE,'user_email':email or ''}
    def page(n):
        body['pageno']=n
        return (yield from post(PROD_URL,dict(body)))
    first=yield from page(1)
    result=list(first.get('list') or [])
    total=first.get('total')
    if isinstance(total,(int,float)) and not isinstance(total,bool):
        if len(result)<total:
            size=max(len(result),PAGE)
            for p in range(2,min(math.ceil(total/size),MAX_PAGES)+1):
                j=yield from page(p)
                result.extend(j.get('list') or [])
    else:
        q=2
        while q<=MAX_PAGES and len(result)>=(q-1)*PAGE:
            j=yield from page(q)
            items=j.get('list') or []
            if not items:break
            result.extend(items);q+=1
    return result


def fetch_tasks(build_url):
    result=[]
    for page in range(1,min(MAX_PAGES,MAX_OFFSET//PAGE+1)+1):
        data=yield from get(build_url(page))
        l=data.get('list') or []
        result.extend(l)
        total=data.get('total')
        if len(l)<PAGE or isinstance(total,(int,float)) and len(result)>=total:break
    return result


def fetch_pack_tasks():
    return (yield from fetch_tasks(lambda page:PACK_URL+'?'+urlencode({'task_status':1,'pageno':page,'count':PAGE})))


def fetch_completed_range(start,end):
    def call(page,size):
        return (yield from get(CHECK_URL+'?'+urlencode({'is_get_total':0,'complete_time_start':start,
                         'complete_time_end':end,'pageno':page,'count':size})))
    try:first=yield from call(1,BIG_PAGE)
    except WMSRequestError as exc:
        if not ('HTTP 400' in str(exc) or 'retcode' in str(exc).lower()):raise
        first=yield from call(1,PAGE)
    rows=list(first.get('list') or []);total=first.get('total');partial=None
    if not rows or isinstance(total,(int,float)) and len(rows)>=total:return {'rows':rows,'partial':None}
    size=len(rows);max_page=min(MAX_PAGES,MAX_OFFSET//size+1)
    if isinstance(total,(int,float)):
        need=math.ceil(total/size);pages=min(need,max_page)
        if need>max_page:partial=f'WMS chỉ cho đọc {max_page*size}/{total} Task.'
        for page in range(2,pages+1):
            try:
                j=yield from call(page,size)
                rows.extend(j.get('list') or [])
            except WMSRequestError as exc:
                partial=partial or str(exc)
        return {'rows':rows,'partial':partial}
    for page in range(2,max_page+1):
        try:
            j=yield from call(page,size)
            l=j.get('list') or []
        except WMSRequestError as exc:
            partial=str(exc);break
        rows.extend(l)
        if len(l)<size:break
    return {'rows':rows,'partial':partial}


def task_station(task):
    sid=task.get('checked_station_id') or task.get('checking_station_id') or task.get('station_id') or ''
    if isinstance(sid,list):sid=sid[0] if sid else ''
    return str(sid).upper()


def fetch_checked_recent(now,wanted):
    bounds=[0,300,600,1200,2100,3600]
    want=set(wanted); found=set();rows=[];partial=None
    for i in range(len(bounds)-1):
        try:part=yield from fetch_completed_range(now-bounds[i+1]+1,now-bounds[i])
        except WMSRequestError as exc:
            if not rows:raise
            partial=partial or str(exc);break
        rows.extend(part['rows']);partial=partial or part['partial']
        for task in part['rows']:
            sid=task_station(task)
            if task.get('operator') and sid in want:found.add(sid)
        if want and len(found)>=len(want):break
    return {'rows':rows,'partial':partial,'complete':len(found)>=len(want)}


def fetch_sort_tasks(start,end,hour_start,wanted):
    def call(page,size):
        return (yield from get(SORT_URL+'?'+urlencode({'task_status':2,'beg_ctime':start,
                         'end_ctime':end,'pageno':page,'count':size})))
    try:first=yield from call(1,BIG_PAGE)
    except WMSRequestError as exc:
        if not ('HTTP 400' in str(exc) or 'retcode' in str(exc).lower()):raise
        first=yield from call(1,PAGE)
    rows=list(first.get('list') or []);total=first.get('total');partial=None
    if not rows:return {'rows':[],'partial':None,'complete':False}
    size=len(rows);wanted=set(wanted);found=set()
    def scan(tasks):
        oldest=float('inf')
        for task in tasks:
            sid=task_station(task)
            if task.get('operator') and sid in wanted:found.add(sid)
            ts=task.get('ctime')
            if ts and ts<oldest:oldest=ts
        return oldest
    def enough(oldest):
        return oldest < hour_start-6*3600 or (len(found)>=len(wanted) and oldest<hour_start-1800)
    if not enough(scan(rows)):
        max_page=min(MAX_SORT_PAGES,MAX_OFFSET//size+1)
        for page in range(2,max_page+1):
            if isinstance(total,(int,float)) and len(rows)>=total:break
            try:j=yield from call(page,size);items=j.get('list') or []
            except WMSRequestError as exc:partial=str(exc);break
            if not items:break
            rows.extend(items)
            if enough(scan(items)) or len(items)<size:break
    return {'rows':rows,'partial':partial,'complete':len(found)>=len(wanted)}
