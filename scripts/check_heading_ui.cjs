const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const elements = new Map();
const element = id => {
 if (!elements.has(id)) elements.set(id,{id,value:'',textContent:'',dataset:{},classList:{toggle(){},add(){}},replaceChildren(){},add(){}});
 return elements.get(id);
};
const modes = ['green','classic','companion','analog'].map(mode => ({id:'mode-card',dataset:{mode},disabled:false,
 setAttribute(name,value){this[name]=value;}}));
const state = {connection:'needs_setup',connection_message:'Test',usage:{status:'unavailable'},provider_status:'Test',
 legacy_candidates:[],config:{heading:'',bind:'',esp32_ip:'',codex_path:''},device:null,csrf:'test'};
const context = vm.createContext({document:{getElementById:element,querySelectorAll(selector){return selector === '.mode-card' ? modes : []; }},Option:function(){},setInterval(){},
 fetch:()=>new Promise(()=>{}),Date,JSON,console});
vm.runInContext(fs.readFileSync('companion/web/app.js','utf8'),context);
for (const heading of ['', 'IROZON DOT', 'Dot', undefined]) {
 state.config.heading=heading; context.render(state,true);
 assert.equal(element('heading').value,heading ?? 'IROZON DOT');
}
assert.deepEqual(modes.map(card=>card.dataset.mode),['green','classic','companion','analog']);
state.connection='connected'; state.device={mode:'analog',display_on:true,mode_name:'Analog Clock'};
context.render(state);
assert.equal(modes[3]['aria-pressed'],'true');
let posted;
context.fetch=async(path,options)=>{
 if(options.method==='POST') {posted=JSON.parse(options.body);state.device.mode=posted.mode;}
 return {ok:true,status:200,json:async()=>options.method==='POST'?{message:'Saved'}:state};
};
(async()=>{
 await modes[2].onclick();
 assert.deepEqual(posted,{mode:'companion'});
 assert.equal(modes[2]['aria-pressed'],'true');
 state.connection='disconnected'; context.unavailable();
 assert(modes.every(card=>card.disabled));
 console.log('PASS: settings JS preserves names, selects each of four modes via existing API, and disables cards offline');
})().catch(error=>{console.error(error);process.exitCode=1;});
