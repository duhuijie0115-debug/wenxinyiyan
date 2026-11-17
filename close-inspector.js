(() => {
 const req = process.mainModule?.require.bind(process.mainModule) || process.getBuiltinModule('module').createRequire(process.cwd()+'/debug-capture.cjs');
 setTimeout(()=>req('node:inspector').close(),150);
 return {closing:true,pid:process.pid};
})()
