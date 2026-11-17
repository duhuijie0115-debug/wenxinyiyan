(() => {
 const req=process.mainModule?.require.bind(process.mainModule)||process.getBuiltinModule('module').createRequire(process.cwd()+'/debug-capture.cjs');
 const electron=req('electron');
 if (!electron.app?.quit) throw Error('Target is not Electron main');
 setTimeout(()=>electron.app.quit(),250);
 return {pid:process.pid,quittingCaptureMode:true};
})()
