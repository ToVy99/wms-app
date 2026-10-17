const $=id=>document.getElementById(id);
async function refresh(){
 const tabs=await chrome.tabs.query({url:'https://wms.ssc.shopee.vn/*'});$('tabs').replaceChildren();
 for(const tab of tabs){const o=document.createElement('option');o.value=tab.id;o.textContent=(tab.title||'WMS')+' · Tab '+tab.id;$('tabs').append(o);}
 if(!tabs.length){const o=document.createElement('option');o.textContent='Chưa có tab WMS đang mở';o.value='';$('tabs').append(o);}
}
async function status(){const s=await chrome.runtime.sendMessage({kind:'status'});$('state').textContent=s.connected?'Đã kết nối · Tab '+s.tabId+(s.busy?' · Đang tải':''):s.error||'Chưa kết nối';$('connect').disabled=s.busy;$('tabs').disabled=s.busy;return s;}
$('refresh').onclick=refresh;
$('connect').onclick=async()=>{if(!$('tabs').value)return;$('state').textContent='Đang kết nối…';await chrome.runtime.sendMessage({kind:'connect',tabId:Number($('tabs').value)});await status();};
$('disconnect').onclick=async()=>{await chrome.runtime.sendMessage({kind:'disconnect'});await status();};
refresh().then(status);setInterval(status,1000);
