(async () => {
 const req = process.mainModule?.require.bind(process.mainModule) || process.getBuiltinModule('module').createRequire(process.cwd()+'/debug-capture.cjs');
 const fs=req('node:fs');
 const path=req('node:path'), root=process.env.WENXINYIYAN_ROOT || process.cwd();
 if (!process.env.WORKBUDDY_INSTALL) throw Error('Set WORKBUDDY_INSTALL to the actual installation directory');
 const payload=JSON.parse(fs.readFileSync(path.join(root,'capture/replay-request.json'),'utf8'));
 const headers=req(path.join(process.env.WORKBUDDY_INSTALL,'resources/app.asar/main/gateway-secret.js')).n();
 const result=await fetch('http://127.0.0.1:63473/api/v1/llm/completions',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const raw=await result.text();
 let body; try {body=JSON.parse(raw);} catch {body={success:false,error:raw};}
 fs.writeFileSync(path.join(root,'capture/replay-response.json'),JSON.stringify({status:result.status,body},null,2));
 return {status:result.status,success:body.success,textLength:body.text?.length};
})()
