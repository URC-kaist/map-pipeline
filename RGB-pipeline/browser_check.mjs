// Dependency-free Chrome DevTools check using Node 24's built-in WebSocket.
import fs from 'node:fs';
const [debugPort, origin, reportPath, screenshotPath] = process.argv.slice(2);
const pages=await fetch(`http://127.0.0.1:${debugPort}/json/list`).then(r=>r.json());
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
let id=0;const pending=new Map(),requests=[],failures=[],external=[],exceptions=[];
function call(method,params={}){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))})}
ws.onmessage=async ({data})=>{
 const m=JSON.parse(data);
 if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);return}
 if(m.method==='Fetch.requestPaused'){
  const u=m.params.request.url;const allowed=u.startsWith(origin+'/')||u.startsWith('data:')||u.startsWith('blob:');
  if(!allowed)external.push(u);
  await call(allowed?'Fetch.continueRequest':'Fetch.failRequest',{requestId:m.params.requestId,...(allowed?{}:{errorReason:'BlockedByClient'})});
 }
 if(m.method==='Network.requestWillBeSent')requests.push(m.params.request.url);
 if(m.method==='Network.responseReceived'&&m.params.response.status>=400)failures.push(m.params.response);
 if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params.exceptionDetails);
};
await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
await call('Network.setCacheDisabled',{cacheDisabled:true});
await call('Fetch.enable',{patterns:[{urlPattern:'*'}]});
await call('Emulation.setDeviceMetricsOverride',{width:1200,height:850,deviceScaleFactor:1,mobile:false});
await call('Page.navigate',{url:origin+'/'});
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function ready(){return evaluate(`new Promise((resolve,reject)=>{const end=Date.now()+30000;const tick=()=>{const m=window.offlineMap;if(m&&m.loaded()&&m.areTilesLoaded())resolve({zoom:m.getZoom(),center:m.getCenter()});else if(Date.now()>end)reject(new Error(document.querySelector('#status').textContent));else setTimeout(tick,100)};setTimeout(tick,500)})`)}
const overview=await ready();
const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(screenshotPath,Buffer.from(shot.data,'base64'));
const zoomChecks=[];
for(const z of [14,15,16,17]){await evaluate(`offlineMap.jumpTo({zoom:${z},center:[-110.77096,38.4025]}); true`);zoomChecks.push(await ready());}
await evaluate('offlineMap.jumpTo({zoom:22,center:[-110.77096,38.4025]}); true');const overzoom=await ready();
await evaluate('offlineMap.panBy([100,80],{duration:0}); true');const panned=await ready();
const tileRequests=requests.filter(u=>/\/tiles\/naip\/\d+\/\d+\/\d+\.png/.test(u));
const requestedZooms=[...new Set(tileRequests.map(u=>Number(u.match(/\/naip\/(\d+)\//)[1])))].sort((a,b)=>a-b);
const report={overview,zoomChecks,overzoom,panned,requestedZooms,tileRequests:tileRequests.length,externalRequests:external,httpFailures:failures,exceptions,
 external_network:'Page requests intercepted: only this localhost origin, blob and data allowed; cache disabled',
 passed:external.length===0&&failures.length===0&&exceptions.length===0&&tileRequests.length>0&&requestedZooms.every(z=>z>=14&&z<=18)&&overzoom.zoom===22};
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));ws.close();if(!report.passed)process.exitCode=1;
