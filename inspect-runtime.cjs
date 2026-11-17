const fs=require('node:fs');
(async()=>{
  const port=Number(process.argv[2]||9229), file=process.argv[3];
  const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const target=targets.find(t=>t.type==='node')||targets[0];
  if(!target) throw Error('No debugger target');
  const ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
  const expression=file?fs.readFileSync(file,'utf8'):'({pid:process.pid,requireType:typeof require})';
  const timer=setTimeout(()=>{ws.close();process.exitCode=1;console.error('Inspector timed out');},20000);
  ws.addEventListener('message',e=>{const m=JSON.parse(String(e.data));if(m.id===1){clearTimeout(timer);console.log(JSON.stringify(m.result??m.error));ws.close();}});
  ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression,returnByValue:true,awaitPromise:true}}));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
