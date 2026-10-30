#!/bin/sh
# Second turn of a custom-tool exchange as the request input: the user's ask, the model's earlier
# custom_tool_call and its custom_tool_call_output; expects a 200 with an assistant message.
H=${1:-gammaweb09.medien.uni-weimar.de}
KEY=${MODEL_KEY:?set MODEL_KEY to the server's --api-key}
curl -sS -m 90 -X POST "http://$H:31726/v1/responses" -H "Authorization: Bearer $KEY" -H "content-type: application/json" -d '{
 "model": "gpt-oss-20b",
 "input": [
   {"type": "message", "role": "user", "content": "Add a file hello.txt containing the line hi, using the apply_patch tool, then tell me in one sentence what you did."},
   {"type": "custom_tool_call", "call_id": "call_test1", "name": "apply_patch", "input": "*** Begin Patch\n*** Add File: hello.txt\n+hi\n*** End Patch"},
   {"type": "custom_tool_call_output", "call_id": "call_test1", "output": "Success. Updated the following files:\nA hello.txt"}
 ],
 "tools": [{"type": "custom", "name": "apply_patch", "description": "Apply a patch in the *** Begin Patch / *** End Patch format. The input is the patch text.", "format": {"type": "text"}}],
 "reasoning": {"effort": "low"}, "max_output_tokens": 200}' | python3 -c "
import json, sys; r = json.load(sys.stdin)
if 'error' in r: print('ERROR', r['error']); sys.exit(1)
print('status', r.get('status'))
for o in r.get('output', []): print(' -', o.get('type'), o.get('name', ''), repr((o.get('input') or (o.get('content') or [{}])[0].get('text', '')))[:200])"
