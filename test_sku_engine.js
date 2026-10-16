const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(0,'utf8');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function run(handler,options={}){
 const log=[],counts={},active={order:0,task:0},peak={order:0,task:0};let cancel=false;
 const sandbox={AbortController,Date,Promise,Map,Set,Array,Object,String,Number,Math,Error,setTimeout,clearTimeout,setInterval,clearInterval,
  window:{__intraSkuCancelled:async()=>cancel,__intraSkuProgress:async(_,message)=>{if(options.cancel&&message.includes('0/'))setTimeout(()=>cancel=true,20)}},
  fetch:async(url,opt)=>{
   const kind=url.includes('search_order')?'order':'task',body=JSON.parse(opt.body),key=kind+':'+(body.search_key_two||'')+':'+body.pageno;
   assert.equal(opt.credentials,'include');assert.equal(opt.headers['X-CCTV-Tenant-Id'],'WMS');
   log.push({kind,body,key});counts[key]=(counts[key]||0)+1;active[kind]++;peak[kind]=Math.max(peak[kind],active[kind]);
   try{
    await new Promise((resolve,reject)=>{
     const abort=()=>{clearTimeout(timer);reject(new Error('aborted'))};
     const timer=setTimeout(()=>{opt.signal.removeEventListener('abort',abort);resolve()},options.cancel&&kind==='task'?250:15);
     if(opt.signal.aborted)abort();else opt.signal.addEventListener('abort',abort,{once:true});
    });
    const payload=handler(kind,body,counts[key]);
    if(payload.http)return {ok:false,status:payload.http};
    return {ok:true,json:async()=>payload};
   }finally{active[kind]--;}
  }};
 const result=await vm.runInNewContext('('+source+')',sandbox)({upc:'00123',requestId:'sku-fixture'});
 await wait(30);assert.equal(active.order+active.task,0);
 return {result:JSON.parse(JSON.stringify(result)),log,counts,peak};
}
const ok=data=>({retcode:0,data});
const orders=sns=>ok({total:1,list:[{order_number:'O',shopee_order_sn:sns}]});
(async()=>{
 let r=await run((kind,b)=>{
  if(kind==='order'){assert.equal(b.sku_upc_code,'00123');assert.equal(b.order_status_list,'3');assert.equal(b.count,20);assert.equal(b.is_get_total,b.pageno===1?1:0);return ok({total:140,list:[{order_number:'O'+b.pageno,shopee_order_sn:b.pageno===1?['S0','S1']:['S'+b.pageno]}]})}
  assert.equal(b.end_time-b.start_time+1,7*86400);assert.deepEqual(b.fulfillment_chain_dest_zone_list,[]);
  return ok({total:b.search_key_two==='S0'?21:1,list:[{sub_pickup_id:b.search_key_two==='S1'?'S2':b.search_key_two}]});
 });
 assert.equal(r.result.success,true);assert.equal(r.peak.order,5);assert.equal(r.peak.task,6);
 assert.equal(r.result.data.sns.length,8);assert.equal(r.result.data.tasks.S2.sns.length,2);assert.equal(r.log.length,16);
 console.log('PASS: real overlap, 5 order pages / 6 task SNs, pagination, dedup, payloads');
 r=await run((k,b,n)=>k==='order'?orders(['S0','S1','S2']):b.search_key_two==='S0'?ok({total:0,list:null}):b.search_key_two==='S1'?(b.pageno===1?ok({total:21,list:[{sub_pickup_id:'DISCARD'}]}):{http:503}):ok({total:1,list:[{sub_pickup_id:'KEEP'}]}));
 assert.equal(r.result.success,true);assert.deepEqual(r.result.data.failed,['S1']);assert.deepEqual(r.result.data.not_found,['S0']);assert.deepEqual(Object.keys(r.result.data.tasks),['KEEP']);assert.equal(r.counts['task:S1:2'],3);
 console.log('PASS: partial errors, retry twice, no partial SN leakage, null list');
 r=await run((k,b,n)=>k==='order'?(n<3?{http:502}:ok({total:0})):ok({}));
 assert.equal(r.result.success,true);assert.equal(r.log.length,3);assert.equal(r.result.data.orders,0);
 r=await run(()=>({http:500}));assert.equal(r.result.success,false);assert.equal(r.log.length,3);
 r=await run(k=>k==='order'?orders(['S0','S1','S2','S3','S4','S5','S6']):({retcode:10001}));assert.equal(r.result.auth,true);assert(r.log.length<=7);
 console.log('PASS: recovery, fatal order error and auth without retries');
 r=await run(k=>k==='order'?orders(Array.from({length:10},(_,i)=>'S'+i)):ok({total:1,list:[{sub_pickup_id:'T'}]}),{cancel:true});
 assert.equal(r.result.cancelled,true);assert.equal(r.log.length,7);
 console.log('PASS: cancel aborts in-flight fetches and stops pending SNs');
 r=await run(()=>ok({total:2001,list:[]}));assert.equal(r.result.success,false);assert.equal(r.log.length,1);
 r=await run(k=>k==='order'?orders(['S']):ok({total:101,list:[{sub_pickup_id:'T'}]}));assert.equal(r.log.length,6);assert.deepEqual(r.result.data.truncated,['S']);
 console.log('PASS: original 2000-order / 100-task limits');
})().catch(e=>{console.error(e);process.exit(1)});
