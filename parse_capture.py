"""Build sanitized, reviewable API artifacts from the temporary HTTP recorder."""
import json, pathlib, re
root=pathlib.Path(__file__).resolve().parent
out=root/'capture'
rows=[json.loads(line) for line in (out/'traffic.jsonl').read_text(encoding='utf8').splitlines()]
def sanitize(v):
    if isinstance(v,dict):
        return {k:('[REDACTED]' if re.search(r'authorization|cookie|token|secret|password|api[-_]?key|user[-_]?id|machine[-_]?id|private[-_]?data',k,re.I) else sanitize(x)) for k,x in v.items()}
    if isinstance(v,list): return [sanitize(x) for x in v]
    return v
rows=sanitize(rows)
(out/'traffic.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
cloud='https://www.workbuddy.cn/v2/chat/completions'
rq=next(r for r in reversed(rows) if r.get('url')==cloud and r['kind']=='request' and isinstance(r.get('body'),dict))
rp=next(r for r in reversed(rows) if r.get('id')==rq['id'] and r['kind']=='response')
local=next(r for r in rows if r['kind']=='request' and '/api/v1/llm/completions' in r.get('url','') and isinstance(r.get('body'),dict))
def write(name,obj): (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
write('local-request.json',local)
write('cloud-request.json',rq)
write('cloud-response-headers.json',{'status':rp['status'],'headers':rp['headers']})
(out/'cloud-response.sse').write_text(rp['body'],encoding='utf8')
frames=[]; text=[]; reasons=[]; usage=None
for line in rp['body'].splitlines():
    if not line.startswith('data:'): continue
    value=line[5:].strip()
    if value=='[DONE]': continue
    try: frame=json.loads(value)
    except json.JSONDecodeError: continue
    frames.append(frame)
    if frame.get('usage'): usage=frame['usage']
    for choice in frame.get('choices',[]):
        delta=choice.get('delta') or {}
        if isinstance(delta.get('content'),str): text.append(delta['content'])
        if choice.get('finish_reason'): reasons.append(choice['finish_reason'])
requests=[r for r in rows if r.get('url')==cloud and r['kind']=='request']
changed=[k for k,v in rq['headers'].items() if v!=requests[0]['headers'].get(k)]
summary={'cloud_url':cloud,'status':rp['status'],'request_fields':list(rq['body']),
 'request_model':rq['body']['model'],'response_model':frames[0].get('model'),
 'message_roles':[m['role'] for m in rq['body']['messages']],
 'tool_names':[t.get('function',{}).get('name') for t in rq['body'].get('tools',[])],
 'dynamic_headers_observed':changed,'sse_json_frames':len(frames),'sse_done': 'data: [DONE]' in rp['body'],
 'finish_reasons':reasons,'usage':usage,'extracted_text':''.join(text),
 'replay_result':json.loads((out/'replay-response.json').read_text(encoding='utf8'))}
write('summary.json',summary)
(out/'enhanced-prompt.txt').write_text(summary['replay_result']['body']['text'],encoding='utf8')
print(json.dumps({k:v for k,v in summary.items() if k not in ['extracted_text','replay_result']},ensure_ascii=True,indent=2))
