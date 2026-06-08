import json

d = json.load(open(r'tests/self_play/results/run14_full_gpt54mini_beta_squeezed_2.json'))
print('top-level keys:', list(d.keys()))
print()
print('scores section:')
print(json.dumps(d.get('scores'), indent=2)[:800] if d.get('scores') else 'MISSING/EMPTY')
print()
errors = d.get('metadata', {}).get('errors')
print('metadata.errors:', errors if errors else '(none)')
print()
transcript = d.get('transcript', [])
print('transcript entries:', len(transcript))
print()
print('last 3 transcript entries (truncated):')
for entry in transcript[-3:]:
    faction = entry.get('faction', '?')
    rnd = entry.get('round', '?')
    content = (entry.get('content') or entry.get('message') or '')[:300]
    print(f'[R{rnd} {faction}] {content}')
print()
print('llm_call_log entries:', len(d.get('llm_call_log', [])))
# Look for the failed scoring call
for call in d.get('llm_call_log', []):
    if call.get('purpose') and 'scor' in call.get('purpose', '').lower():
        print()
        print('SCORING call attempt:')
        print('  purpose:', call.get('purpose'))
        print('  success:', call.get('success'))
        print('  error:', call.get('error'))
        resp = call.get('response_text', call.get('response', ''))[:500]
        print('  response snippet:', resp)
