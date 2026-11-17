(() => {
  const req = process.mainModule?.require.bind(process.mainModule) || process.getBuiltinModule?.('module').createRequire(process.cwd() + '/debug-capture.cjs');
  if (!req) throw Error('No module loader');
  const hook = req('node:path').join(process.env.WENXINYIYAN_ROOT || process.cwd(), 'capture-hook.cjs');
  req(hook);
  const cp = req('node:child_process'), spawn = cp.spawn;
  if (!cp.__workbuddyCaptureSpawn) {
    cp.__workbuddyCaptureSpawn = true;
    cp.spawn = function(command, args, options) {
      if (/WorkBuddy\.exe$/i.test(command) && options?.env?.ELECTRON_RUN_AS_NODE === '1' && Array.isArray(args) && !args.includes(hook)) {
        args = ['--require', hook, ...args];
      }
      return Reflect.apply(spawn, this, [command, args, options]);
    };
  }
  return {pid: process.pid, attached: true};
})()
