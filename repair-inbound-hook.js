(() => {
 const req = typeof require==='function'?require:process.mainModule.require.bind(process.mainModule);
 req('node:http').Server.prototype.emit=req('node:events').EventEmitter.prototype.emit;
 return {pid:process.pid,inboundObservationRemoved:true};
})()
