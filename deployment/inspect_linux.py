import pathlib, struct, json
p=next(pathlib.Path('extracted').rglob('app.asar'))
with p.open('rb') as f:
    a=struct.unpack('<4I',f.read(16));j=json.loads(f.read(a[3]));base=8+a[1]
    def walk(d,s=''):
        for k,v in d.get('files',{}).items():
            path=s+'/'+k
            if 'files' in v:yield from walk(v,path)
            elif path.endswith('.js') and 'offset' in v and not v.get('unpacked'):yield path,v
    found=[]
    for name,v in walk(j):
        if not name.startswith('/main/'):continue
        f.seek(base+int(v['offset']));data=f.read(v['size'])
        if b'wb.request' in data or b'wbipcDiscoveryPath' in data:found.append(name)
    print(json.dumps({'asar':str(p),'wbipc_sources':found}))
