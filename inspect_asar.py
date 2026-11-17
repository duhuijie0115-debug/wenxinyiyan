import json, struct, pathlib, re, os
p=pathlib.Path(os.environ['WORKBUDDY_INSTALL'])/'resources/app.asar'
f=p.open('rb'); h=struct.unpack('<4I',f.read(16)); index=json.loads(f.read(h[3])); base=8+h[1]
dest=pathlib.Path('inspection'); dest.mkdir(exist_ok=True)
def walk(d,path=''):
    for name,v in d.get('files',{}).items():
        s=path+'/'+name
        if 'files' in v: yield from walk(v,s)
        elif s.endswith(('.js','.json','.html')) and not v.get('unpacked') and 'offset' in v:
            yield s,v
for s,v in walk(index):
    if s.startswith('/resources/plugins/'): continue
    f.seek(base+int(v['offset'])); data=f.read(v['size']).decode('utf8','replace')
    hits=list(re.finditer(r'提示词优化|优化提示词|optimizePrompt|promptOptimize|prompt-optimi|prompt_optimi',data,re.I))
    if hits:
        target=dest/s.lstrip('/'); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(data,encoding='utf8')
        print(s)
        for m in hits[:15]: print(data[max(0,m.start()-200):m.end()+400])
