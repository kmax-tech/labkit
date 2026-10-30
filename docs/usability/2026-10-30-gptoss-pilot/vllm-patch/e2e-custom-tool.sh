#!/bin/sh
# Minimal end-to-end request: a custom (free-form) tool through the Responses API; expects a custom_tool_call item.
H=${1:-gammaweb05.medien.uni-weimar.de}
curl -sS -m 90 -X POST "http://$H:31726/v1/responses" -H "Authorization: Bearer $KEY" -H "content-type: application/json" -d '{
 "model": "gpt-oss-20b",
 "input": "Use the apply_patch tool to add a file hello.txt containing the line hi. Call the tool now.",
 "tools": [{"type": "custom", "name": "apply_patch", "description": "Apply a patch in the *** Begin Patch / *** End Patch format. The input is the patch text.", "format": {"type": "text"}}],
 "reasoning": {"effort": "low"}, "max_output_tokens": 300}' | python3 -c "
import json, sys; r = json.load(sys.stdin)
if 'error' in r: print('ERROR', r['error']); sys.exit(1)
print('status', r.get('status'))
for o in r.get('output', []): print(' -', o.get('type'), o.get('name', ''), repr((o.get('input') or (o.get('content') or [{}])[0].get('text', '')))[:200])"
