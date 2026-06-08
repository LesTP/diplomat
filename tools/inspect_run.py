import json

d = json.load(open(r'tests/self_play/results/run14_bare_gpt54mini_beta_squeezed_2.json'))
print('bare_mode:', d.get('bare_mode'))
print()
# What did the scorer LLM actually claim?
print('=== SCORER LLM verdict (pre-rescore — original LLM output) ===')
calls = d.get('llm_call_log', [])
last = calls[-1] if calls else {}
print('raw response:')
print((last.get('response_text') or last.get('response') or '')[:1500])
print()
print('=== FINAL ROUND MESSAGES (full text) ===')
transcript = d.get('transcript', [])
for entry in transcript[-3:]:
    faction = entry.get('faction', '?')
    content = entry.get('content') or entry.get('message') or ''
    print(f'--- [{faction}] ({len(content)} chars) ---')
    print(content)
    print()
