(() => {
 const req=process.mainModule?.require.bind(process.mainModule)||process.getBuiltinModule('module').createRequire(process.cwd()+'/debug-capture.cjs');
 const inspector=req('node:inspector');
 setTimeout(()=>{inspector.close();inspector.open(19223,'127.0.0.1',false);},150);
 return {pid:process.pid,nextPort:19223};
})()
