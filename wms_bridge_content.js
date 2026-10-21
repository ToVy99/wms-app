(() => {
if(globalThis.__intraBridgeLoaded)return;globalThis.__intraBridgeLoaded=true;
const jobs=new Map();
const emit=message=>chrome.runtime.sendMessage(message);
window.__intraSkuCancelled=async id=>!jobs.has(id)||jobs.get(id).cancelled;
window.__intraSkuProgress=async(id,text)=>{if(jobs.has(id))await emit({kind:'progress',id,text});};
const allowed=new Set(['/api/v2/apps/process/outbound/salesorder/search_order','/api/v2/apps/basic/reportcenter/create_export_task','/api/v2/apps/basic/reportcenter/search_export_task','/api/v2/apps/process/taskcenter/pickingtask/search_sales_sub_picking_task',
'/mgmt/api/wms_pc/forward_wms_be/api/v2/openapi/mgmt/workspace/pc/data_wms__warehouse_operation_whs__outbound_productivity_info_ri',
'/api/v2/apps/process/taskcenter/checkingtask/search_checking_task',
'/api/v2/apps/process/taskcenter/sortingtask/search_sorting_task',
'/api/v2/apps/process/outbound/packing/search_packing_task']);
const cotFetch=async ({url, method, body, binary}) => {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), binary ? 90000 : 25000);
  try {
    const opt = {method, credentials:'include', signal:ctrl.signal};
    if (!binary) opt.headers = {'Content-Type':'application/json;charset=UTF-8','X-CCTV-Tenant-Id':'WMS'};
    if (method === 'POST') opt.body = JSON.stringify(body);
    const resp = await fetch(url, opt);
    if (!resp.ok) throw new Error('HTTP '+resp.status+(resp.status===429?' · WMS giới hạn yêu cầu; đã dừng.':''));
    if (binary) {
      const bytes = new Uint8Array(await resp.arrayBuffer());
      let text='';
      for(let i=0;i<bytes.length;i+=32768) text+=String.fromCharCode(...bytes.subarray(i,i+32768));
      return {success:true,data:btoa(text)};
    }
    let res;
    try {res=await resp.json()} catch {return {success:false,error:'WMS không trả JSON. Hãy kiểm tra đăng nhập trong Chrome.',auth:true}}
    if(res && res.retcode===0) return {success:true,data:res.data??{}};
    return {success:false,error:res?.message||'Lỗi WMS',auth:res?.retcode===10001};
  } catch(e) {return {success:false,error:e.name==='AbortError'?'WMS phản hồi quá lâu; đã dừng, không tự thử lại.':e.message}}
  finally {clearTimeout(timer)}
};
const skuSearch=async ({upc, requestId}) => {
  const root='https://wms.ssc.shopee.vn/api/v2/apps/process/';
  const orderUrl=root+'outbound/salesorder/search_order';
  const taskUrl=root+'taskcenter/pickingtask/search_sales_sub_picking_task';
  const controller=new AbortController();
  let cancelled=false, fatal=null, checking=false, requests=0;
  const check=async()=>{
    if(checking)return;
    checking=true;
    try {if(await window.__intraSkuCancelled(requestId)){cancelled=true;controller.abort();}}
    finally {checking=false;}
  };
  const timer=setInterval(()=>{check().catch(()=>{cancelled=true;controller.abort();});},100);
  const stopped=()=>{if(cancelled)throw new Error('Đã dừng tìm');if(fatal)throw fatal;};
  const progress=message=>window.__intraSkuProgress(requestId,message);
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  async function api(url,body){
    for(let attempt=0;attempt<=2;attempt++){
      stopped();
      try{
        requests++;
        const resp=await fetch(url,{method:'POST',credentials:'include',
          headers:{'Content-Type':'application/json;charset=UTF-8','X-CCTV-Tenant-Id':'WMS'},
          signal:controller.signal,body:JSON.stringify(body)});
        if(!resp.ok)throw new Error('HTTP '+resp.status);
        let res;
        try{res=await resp.json();}
        catch{const e=new Error('Phản hồi không hợp lệ (có thể chưa đăng nhập WMS)');e.auth=true;throw e;}
        if(res && res.retcode===0 && res.data)return res.data;
        if(res && res.retcode===10001){const e=new Error('Chưa đăng nhập WMS!');e.auth=true;throw e;}
        throw new Error(res?.message || 'Lỗi lấy dữ liệu');
      }catch(e){
        stopped();
        if(e.auth){fatal=e;controller.abort();throw e;}
        if(attempt===2)throw e;
        await sleep(200*(attempt+1));
      }
    }
  }
  try{
    await check();stopped();
    await progress(upc+' · Đang lấy đơn Picked…');
    const body=p=>({sku_upc_code:upc,order_status_list:'3',pageno:p,count:20,is_get_total:p===1?1:0});
    const first=await api(orderUrl,body(1));
    const total=Number(first.total)||0, pages=Math.ceil(total/20), orders=new Map();
    if(pages>100)throw new Error('Quá nhiều đơn ('+total+'), vượt giới hạn 2000');
    const add=d=>(d.list||[]).forEach(o=>orders.set(o.order_number,o));
    add(first);
    for(let start=2;start<=pages;start+=5){
      stopped();
      const batch=Array.from({length:Math.min(5,pages-start+1)},(_,i)=>start+i);
      const results=await Promise.all(batch.map(p=>api(orderUrl,body(p))));
      results.forEach(add);
      await progress(upc+' · Đã lấy '+Math.min(start+4,pages)+'/'+pages+' trang đơn');
    }
    const snSet=new Set();
    orders.forEach(o=>{const v=o.shopee_order_sn;(Array.isArray(v)?v:[v]).forEach(s=>{if(s&&String(s).trim())snSet.add(String(s).trim());});});
    const sns=[...snSet], tasks=new Map(), notFound=[], failed=[], truncated=[];
    const day=Math.floor((Date.now()+7*3600000)/86400000)*86400000-7*3600000;
    const win={start_time:Math.floor((day-6*86400000)/1000),end_time:Math.floor((day+86400000)/1000)-1};
    let index=0,done=0;
    async function worker(){
      while(index<sns.length&&!cancelled&&!fatal){
        const sn=sns[index++],rows=[];let capped=false;
        try{
          for(let pageno=1;pageno<=5;pageno++){
            stopped();
            const d=await api(taskUrl,{search_key_two:sn,...win,fulfillment_chain_dest_zone_list:[],pageno,count:20});
            rows.push(...(d.list||[]));
            const more=pageno*20<(Number(d.total)||0);
            if(!more)break;
            if(pageno===5)capped=true;
          }
          stopped();
          if(capped)truncated.push(sn);
          if(!rows.length)notFound.push(sn);
          rows.forEach(task=>{const key=String(task.sub_pickup_id??'');let e=tasks.get(key);if(!e){e={task,sns:new Set()};tasks.set(key,e);}e.sns.add(sn);});
        }catch(e){
          if(cancelled||fatal||e.auth)return;
          failed.push(sn);
        }
        done++;
        await progress(upc+' · Tra Picking Task · '+done+'/'+sns.length+' SN');
      }
    }
    await progress(upc+' · Tra Picking Task · 0/'+sns.length+' SN');
    await Promise.all(Array.from({length:Math.min(6,sns.length)},worker));
    stopped();
    return {success:true,data:{upc,total_api:total,orders:orders.size,sns,
      tasks:Object.fromEntries([...tasks].map(([k,v])=>[k,{task:v.task,sns:[...v.sns]}])),
      not_found:notFound,failed,truncated},requests};
  }catch(e){controller.abort();return {success:false,cancelled,error:e.message,auth:!!e.auth,requests};}
  finally{clearInterval(timer);}
};

async function result(id,value){
 const raw=JSON.stringify(value);await emit({kind:'result_start',id});let seq=0;
 for(let i=0;i<raw.length;){let end=Math.min(i+60000,raw.length);const c=raw.charCodeAt(end-1);if(end<raw.length&&c>=0xD800&&c<=0xDBFF)end--;await emit({kind:'result_chunk',id,seq:seq++,text:raw.slice(i,end)});i=end;}
 await emit({kind:'result_end',id,count:seq});
}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
 if(sender.id!==chrome.runtime.id)return;
 if(m.kind==='cancel'){const job=jobs.get(m.id);if(job)job.cancelled=true;reply({ok:true});return;}
 if(m.kind!=='request')return;
 if(jobs.has(m.id)){reply({accepted:false,error:'Yêu cầu bị trùng'});return;}
 try{
  const q=m.message,u=new URL(q.url);
  if(u.origin!=='https://wms.ssc.shopee.vn'||u.username||u.password||location.origin!==u.origin)throw new Error('URL WMS không hợp lệ');
  if(/\/(login|signin|sso|auth)(\/|$)/i.test(location.pathname))throw new Error('Hãy đăng nhập WMS trước');
  if(q.type==='WMS_DOWNLOAD'){if(!u.pathname.startsWith('/oss_downloads_v2/'))throw new Error('Chỉ tải report WMS');}
  else if(!['WMS_GET','WMS_POST','WMS_SKU_SEARCH'].includes(q.type)||!allowed.has(u.pathname))throw new Error('API không được hỗ trợ');
  if(q.type==='WMS_SKU_SEARCH'&&(u.pathname!=='/api/v2/apps/process/outbound/salesorder/search_order'||typeof q.upc!=='string'||!q.upc.trim()))throw new Error('SKU không hợp lệ');
  jobs.set(m.id,{cancelled:false});reply({accepted:true});
  (async()=>{
   try{const value=q.type==='WMS_SKU_SEARCH'?await skuSearch({upc:q.upc,requestId:m.id}):await cotFetch({url:q.url,method:q.type==='WMS_POST'?'POST':'GET',body:q.body,binary:q.type==='WMS_DOWNLOAD'});await result(m.id,value);}
   catch(e){await result(m.id,{success:false,error:e.message}).catch(()=>{});}
   finally{jobs.delete(m.id);}
  })();
 }catch(e){reply({accepted:false,error:e.message});}
});
})();
