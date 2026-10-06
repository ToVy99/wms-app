"""Native implementation of the IntraCity web 1.4 data rules."""
import copy
import io
import json
import unicodedata
import zipfile
from datetime import datetime, timedelta
from openpyxl import load_workbook

ORIGIN = 'https://wms.ssc.shopee.vn'
URL_ORDER = ORIGIN + '/api/v2/apps/process/outbound/salesorder/search_order'
URL_EXPORT = ORIGIN + '/api/v2/apps/basic/reportcenter/create_export_task'
URL_EXPORT_LIST = ORIGIN + '/api/v2/apps/basic/reportcenter/search_export_task?pageno=1&count=20&export_module=2&task_type=722&is_myself=1'
STATUSES = ['Created','Pending Pick','Picking','Picked','Pick Fail','Checking','Checked','Pre Sorting','Pre Sorted','Sorting','Sorted','Packing','Packed','Shipping','Outbound','Cancel']
DEFAULT_CONFIG = {
 'intra': {'name':'Intra City','channels':[],'cots':[{'id':str(i+1),'name':f'COT {i+1}','start':a,'end':b} for i,(a,b) in enumerate([('20:00','23:00'),('23:00','02:00'),('02:00','16:00'),('16:00','20:00')])]},
 'aha': {'name':'AhaMove','channels':['50033','50044'],'cots':[{'id':str(i+1),'name':f'COT {i+1}','start':a,'end':b} for i,(a,b) in enumerate([('08:00','13:00'),('13:00','18:00'),('18:00','08:00')])]},
 'sdd': {'name':'SDD','channels':['50051'],'cots':[{'id':str(i+1),'name':f'COT {i+1}','start':a,'end':b} for i,(a,b) in enumerate([('18:00','04:00'),('04:00','09:00'),('09:00','13:30'),('13:30','18:00')])]},
 'spxck': {'name':'SPX CK (Cồng kềnh)','channels':['50025'],'previous':True,'cots':[{'id':'daily','name':'17H → 17H','start':'17:00','end':'17:00'}]},
}

def time_range(day, carrier, cot):
    beg = datetime.strptime(day+' '+cot['start'], '%Y-%m-%d %H:%M')
    end = datetime.strptime(day+' '+cot['end'], '%Y-%m-%d %H:%M')
    if carrier.get('previous'):
        beg -= timedelta(days=1)
    elif cot['end'] <= cot['start']:
        end += timedelta(days=1)
    return beg, end

def export_body(beg, end):
    a,b = int(beg.timestamp()),int(end.timestamp())
    extra = dict(beg_ctime=a,end_ctime=b,from_listpage=1,include_sku_list=1,order_type=0,date_ref=0,time_from=a,time_to=b)
    return dict(export_module=2,task_type=722,extra_data=json.dumps(extra,separators=(',',':')))

def choose_job(jobs, old_ids, started, task_id=None):
    if task_id is not None:
        return next((j for j in jobs if str(j.get('task_id'))==str(task_id)),None)
    fresh = [j for j in jobs if str(j.get('task_id')) not in old_ids and float(j.get('ctime') or 0)>=started-10]
    if len(fresh)>1:
        raise ValueError('Có nhiều Export cùng lúc; đã dừng để tránh lấy nhầm report.')
    return fresh[0] if fresh else None

def norm(v):
    return unicodedata.normalize('NFC',str(v or '').strip().lower())

def carrier_match(key, service, state):
    v = norm(service)
    if key=='intra':
        return v in ('spx express','spx express ndd - trong ngày') and norm(state) in ('hà nội','thành phố hà nội')
    if key=='aha':
        return v in ('ahamove','ahamove sbs') or v.startswith(('ahamove -','ahamove sbs -'))
    if key=='sdd':
        return v=='spx express sbs trong ngày' or v.startswith(('spx express sbs trong ngày -','spx express sbs - trong ngày'))
    if key=='spxck':
        return v=='spx - hàng cồng kềnh'
    raise ValueError('Không có bộ lọc nhóm '+key)

def parse_report(data, name, key):
    # Detect both a direct XLSX and an outer ZIP, independently of file suffix.
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if 'xl/workbook.xml' not in z.namelist():
            inner = next((n for n in z.namelist() if n.lower().endswith('.xlsx')),None)
            if not inner: raise ValueError('ZIP không có file XLSX.')
            data = z.read(inner)
    wb = load_workbook(io.BytesIO(data),read_only=True,data_only=True)
    try:
        sheet = wb.worksheets[0]
        # WMS reports can declare dimension=A1 while containing 67 columns
        # and thousands of rows. Read actual cells instead of trusting bounds.
        sheet.reset_dimensions()
        rows = sheet.iter_rows(values_only=True)
        headers = next(rows,None)
        if headers is None: raise ValueError('Report không có tiêu đề.')
        indices = {str(v or '').strip():i for i,v in enumerate(headers)}
        required = ['WMS Order No','Status','New 3PL'] + (['Buyer State'] if key=='intra' else [])
        for col in required:
            if col not in indices: raise ValueError('Report thiếu '+col)
        grouped = {}; raw = filtered = 0
        for row in rows:
            def get(col):
                i = indices.get(col)
                return row[i] if i is not None and i<len(row) and row[i] is not None else ''
            ob = str(get('WMS Order No')).strip()
            if not ob: continue
            raw += 1
            if not carrier_match(key,get('New 3PL'),get('Buyer State')): continue
            filtered += 1
            if ob not in grouped:
                status = str(get('Status')).strip()
                code = next((i for i,s in enumerate(STATUSES) if s.lower()==status.lower()),status)
                grouped[ob] = dict(order_number=ob,order_status=code,status_text=status,wave_type=str(get('Wave Type')).strip(),sns=set(),picking=set(),bsks=set(),area='-',ctime_text=str(get('Create Time')),cutoff_text=str(get('Cut off Time')))
            o = grouped[ob]
            for col,dest in [('Shopee order SN','sns'),('Picking ID','picking'),('Device ID','bsks'),('Basket ID','bsks')]:
                v = get(col)
                if v: o[dest].add(str(v))
        return dict(orders=[o for o in grouped.values() if o['order_status']!=15],rawRows=raw,filteredRows=filtered)
    finally:
        wb.close()

def status_name(code):
    return STATUSES[code] if isinstance(code,int) and 0<=code<len(STATUSES) else str(code)

def progress(orders):
    done = sum(o['order_status']==14 for o in orders)
    return done,len(orders),100*done/len(orders) if orders else 0

