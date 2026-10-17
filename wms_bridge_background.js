const HOST='vn.intracity.wms_bridge';
let port=null,selectedTab=null,connected=false,lastError='',heartbeat=null;
const active=new Map();
function send(message){try{if(port)port.postMessage(message);}catch(_){} }
function status(){return {connected,tabId:selectedTab,error:lastError,busy:active.size>0};}
function fail(id,error){send({kind:'result_start',id});send({kind:'result_chunk',id,seq:0,text:JSON.stringify({success:false,error})});send({kind:'result_end',id,count:1});active.delete(id);}
async function disconnect(reason='Đã ngắt kết nối. Chọn tab WMS rồi bấm Kết nối khi cần.'){
  for(const [id,tabId] of active)chrome.tabs.sendMessage(tabId,{kind:'cancel',id}).catch(()=>{});
  send({kind:'state',connected:false,text:reason});
  active.clear();connected=false;selectedTab=null;lastError=reason;
  if(heartbeat)clearInterval(heartbeat);heartbeat=null;
  const old=port;port=null;if(old)old.disconnect();
}
async function connect(tabId){
  if(active.size)throw new Error('Đang tải; hãy đợi hoàn tất hoặc Dừng tìm trước khi đổi tab.');
  const tab=await chrome.tabs.get(tabId);
  if(!tab.url?.startsWith('https://wms.ssc.shopee.vn/'))throw new Error('Hãy chọn tab WMS.');
  if(/\/(login|signin|sso|auth)(\/|$)/i.test(new URL(tab.url).pathname))throw new Error('Hãy đăng nhập và chọn kho trước.');
  await disconnect();selectedTab=tabId;lastError='Đang kết nối app…';
  await chrome.scripting.executeScript({target:{tabId},files:['content.js']});
  const native=chrome.runtime.connectNative(HOST);port=native;
  native.onDisconnect.addListener(()=>{
    if(port!==native)return;
    lastError=chrome.runtime.lastError?.message||'App đã đóng hoặc cầu nối đã ngắt.';
    for(const [id,target] of active)chrome.tabs.sendMessage(target,{kind:'cancel',id}).catch(()=>{});
    active.clear();connected=false;selectedTab=null;port=null;if(heartbeat)clearInterval(heartbeat);heartbeat=null;
  });
  native.onMessage.addListener(async message=>{
    if(port!==native)return;
    if(message.kind==='ready'){
      connected=true;lastError='';send({kind:'state',connected:true,text:'Tiện ích Chrome · '+tab.title+' · Tab '+tabId});
      heartbeat=setInterval(()=>send({kind:'heartbeat'}),20000);return;
    }
    if(message.kind==='disconnect'){await disconnect();return;}
    if(message.kind==='cancel'){
      const target=active.get(message.id);if(target!==undefined)chrome.tabs.sendMessage(target,message).catch(()=>{});return;
    }
    if(message.kind!=='request')return;
    const id=message.id;
    try{
      if(!connected||selectedTab===null)throw new Error('Chưa chọn tab WMS.');
      const current=await chrome.tabs.get(selectedTab);
      if(!current.url?.startsWith('https://wms.ssc.shopee.vn/'))throw new Error('Tab đã chuyển khỏi WMS.');
      active.set(id,selectedTab);
      const reply=await chrome.tabs.sendMessage(selectedTab,message);
      if(!reply?.accepted)throw new Error(reply?.error||'Không nhận được yêu cầu trong tab WMS.');
    }catch(e){fail(id,e.message);}
  });
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  // Only this extension's popup may pick the session. Content frames only return results.
  const fromPopup=sender.id===chrome.runtime.id&&sender.url===chrome.runtime.getURL('popup.html');
  if(sender.tab&&!fromPopup){
    if(sender.tab.id!==selectedTab||sender.frameId!==0||sender.origin!=='https://wms.ssc.shopee.vn'||!active.has(message.id)){reply({ok:false});return;}
    if(['progress','result_start','result_chunk','result_end'].includes(message.kind)){
      send(message);if(message.kind==='result_end')active.delete(message.id);reply({ok:true});
    }else reply({ok:false});
    return;
  }
  if(!fromPopup){reply({ok:false});return;}
  if(message.kind==='status'){reply(status());return;}
  if(message.kind==='connect'){connect(Number(message.tabId)).then(()=>reply(status())).catch(e=>{lastError=e.message;reply(status());});return true;}
  if(message.kind==='disconnect'){disconnect().then(()=>reply(status()));return true;}
});
function tabLost(tabId){
  if(tabId!==selectedTab)return;
  disconnect('Tab WMS đã đóng hoặc tải lại. Hãy chọn đúng kho rồi kết nối lại.');
}
chrome.tabs.onRemoved.addListener(tabLost);
chrome.tabs.onUpdated.addListener((id,change)=>{if(change.status==='loading')tabLost(id);});
