import json, urllib.request
sys_p = open('/scratch/project_2020845/imadh/whatisit/teacher_sample.py').read().split('TEACHER_SYSTEM_PROMPT = """')[1].split('"""')[0]
for i, q in enumerate(["I want to find files in tree/ with the same device and inode as linked.txt.", "Show the hardware cache-line size."]):
    p = {'model': 'teacher', 'temperature': 0.7, 'top_p': 0.95, 'max_tokens': 16384, 'seed': 1000 + i,
         'messages': [{'role': 'system', 'content': sys_p}, {'role': 'user', 'content': q}]}
    r = urllib.request.Request('http://127.0.0.1:8000/v1/chat/completions', json.dumps(p).encode(), {'Content-Type': 'application/json'})
    d = json.load(urllib.request.urlopen(r, timeout=600)); m = d['choices'][0]['message']; c = m.get('content') or ''
    print('keys', list(m), '| think_open', '<think>' in c, '| think_close', '</think>' in c, '| toks', d['usage']['completion_tokens'], '| finish', d['choices'][0]['finish_reason'])
    print('reasoning field:', str(m.get('reasoning') or m.get('reasoning_content'))[:160])
    print('CONTENT[:500]:', c[:500]); print('---')
