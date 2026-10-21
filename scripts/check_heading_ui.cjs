const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const elements = new Map();
const element = id => {
 if (!elements.has(id)) elements.set(id,{value:'',dataset:{},classList:{toggle(){},add(){}},replaceChildren(){},add(){}});
 return elements.get(id);
};
const state = {connection:'needs_setup',connection_message:'Test',usage:{status:'unavailable'},provider_status:'Test',
 legacy_candidates:[],config:{heading:'',bind:'',esp32_ip:'',codex_path:''},device:null,csrf:'test'};
const context = vm.createContext({document:{getElementById:element},Option:function(){},setInterval(){},
 fetch:()=>new Promise(()=>{}),Date,JSON,console});
vm.runInContext(fs.readFileSync('companion/web/app.js','utf8'),context);
for (const heading of ['', 'IROZON DOT', 'Dot', undefined]) {
 state.config.heading=heading; context.render(state,true);
 assert.equal(element('heading').value,heading ?? 'IROZON DOT');
}
let posted;
context.fetch=async(path,options)=>{
 if(options.method==='POST') {posted=JSON.parse(options.body);state.config.heading=posted.heading;}
 return {ok:true,status:200,json:async()=>options.method==='POST'?{message:'Saved'}:state};
};
element('heading').value='   ';
element('name-form').onsubmit({preventDefault(){},submitter:element('save-name')});
setImmediate(()=>setImmediate(()=>{
 assert.equal(posted.heading,'');assert.equal(element('heading').value,'');
 console.log('PASS: actual settings JS preserves empty on reload, defaults only missing values and trims submitted whitespace');
}));
