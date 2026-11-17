'use strict';
// Temporary preload for WorkBuddy Node processes. Captures only enhancement traffic.
const fs = require('node:fs');
const path = require('node:path');
const output = path.join(__dirname, 'capture', 'traffic.jsonl');
fs.mkdirSync(path.dirname(output), { recursive: true });
const redact = value => {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, /authorization|cookie|token|secret|password|api[-_]?key|user[-_]?id|machine[-_]?id/i.test(k) ? '[REDACTED]' : redact(v)]));
  return value;
};
const save = event => { try { fs.appendFileSync(output, JSON.stringify(redact({time: new Date().toISOString(), pid: process.pid, ...event})) + '\n'); } catch {} };
const wanted = url => /\/api\/v1\/llm\/completions(?:\?|$)|https:\/\/www\.workbuddy\.cn\/v2\/chat\/completions(?:\?|$)/.test(url);
const limit = 2 * 1024 * 1024;
function recorder() {
  const chunks = []; let size = 0;
  return { add(c, encoding) { if(c != null && typeof c !== 'function') { try { const b = Buffer.isBuffer(c) ? c : Buffer.from(c, typeof encoding === 'string' ? encoding : undefined); if (size < limit) chunks.push(b.subarray(0, limit-size)); size += b.length; } catch {} } }, result(encoding) { let raw=Buffer.concat(chunks); if(encoding==='gzip' && size<=limit) { try {raw=require('node:zlib').gunzipSync(raw);} catch {return {bodyBase64:raw.toString('base64'),bytes:size,decodeError:true};} } const body = raw.toString('utf8'); try {return {body: JSON.parse(body), bytes:size, truncated:size>limit};} catch {return {body,bytes:size,truncated:size>limit};} } };
}
function watchResponse(res, meta) {
  const body = recorder();
  res.on('data', c => body.add(c));
  res.on('end', () => save({...meta,kind:'response',status:res.statusCode,headers:res.headers,...body.result()}));
}
for (const name of ['node:http','node:https']) {
  const mod = require(name); const original = mod.request;
  mod.request = function(...args) {
    const req = Reflect.apply(original,this,args);
    const url = (req.protocol || (name==='node:https'?'https:':'http:'))+'//'+req.getHeader('host')+req.path;
    if(wanted(url)) {
      const id = require('node:crypto').randomUUID(), body = recorder();
      const write=req.write, end=req.end;
      req.write=function(c,e,...rest){body.add(c,e);return Reflect.apply(write,this,[c,e,...rest]);};
      req.end=function(c,e,...rest){body.add(c,e);save({kind:'request',id,url,method:req.method,headers:req.getHeaders(),...body.result(req.getHeader('content-encoding'))});return Reflect.apply(end,this,[c,e,...rest]);};
      req.prependOnceListener('response',res=>watchResponse(res,{id,url}));
      req.once('error',err=>save({kind:'error',id,url,error:err.message}));
    }
    return req;
  };
}
// Node's built-in fetch uses Undici rather than http.request.
if (typeof globalThis.fetch === 'function') {
  const original=globalThis.fetch;
  globalThis.fetch=async function(input,init) {
    const url=typeof input==='string'?input:String(input.url??input);
    if(!wanted(url)) return Reflect.apply(original,this,arguments);
    const id=require('node:crypto').randomUUID();
    save({kind:'request',id,url,method:init?.method??input?.method??'GET',headers:Object.fromEntries(new Headers(init?.headers??input?.headers)),body:typeof init?.body==='string'?init.body:'[stream or absent]'});
    const response=await Reflect.apply(original,this,arguments);
    response.clone().text().then(body=>save({kind:'response',id,url,status:response.status,headers:Object.fromEntries(response.headers),body:body.slice(0,limit),truncated:body.length>limit})).catch(err=>save({kind:'error',id,url,error:err.message}));
    return response;
  };
}
// Observe the local sidecar's inbound request without modifying the body.
const Server = require('node:http').Server, emit=Server.prototype.emit;
Server.prototype.emit=function(event,...args) {
  if(event==='request' && wanted(args[0].url)) {
    const [req,res]=args, id=require('node:crypto').randomUUID(), body=recorder();
    // Do not attach data listeners here: asynchronous middleware may not yet
    // have attached its parser. The daemon's outgoing hook records this body.
    const rb=recorder(), write=res.write,end=res.end;
    res.write=function(c,e,...rest){rb.add(c,e);return Reflect.apply(write,this,[c,e,...rest]);};
    res.end=function(c,e,...rest){rb.add(c,e);save({kind:'inbound-response',id,status:res.statusCode,...rb.result()});return Reflect.apply(end,this,[c,e,...rest]);};
  }
  return Reflect.apply(emit,this,[event,...args]);
};
save({kind:'hook-ready'});
