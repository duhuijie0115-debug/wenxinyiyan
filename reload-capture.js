(() => {
 const req=typeof require==='function'?require:process.mainModule.require.bind(process.mainModule);
 const hook=req('node:path').join(process.env.WENXINYIYAN_ROOT || process.cwd(), 'capture-hook.cjs');
 delete req.cache[req.resolve(hook)];
 req(hook);
 return {pid:process.pid,gzipCaptureEnabled:true};
})()
