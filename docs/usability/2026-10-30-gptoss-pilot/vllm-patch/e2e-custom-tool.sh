#!/bin/sh
# E2E test (single): see e2e_body.py for the request. Env: MODEL_KEY (the api key of the server),
# MODEL_NAME (default gpt-oss-20b); arg 1: host. Expects a custom_tool_call item (single=single) or a 200
# with an assistant message after the call and its output were sent as input (roundtrip).
H=${1:-gammaweb09.medien.uni-weimar.de}
KEY=${MODEL_KEY:?set MODEL_KEY to the api key of the server}
D=$(dirname "$0")
curl -sS -m 120 -X POST "http://$H:31726/v1/responses" -H "Authorization: Bearer $KEY" -H "content-type: application/json" -d "$(python3 "$D/e2e_body.py" single)" | python3 -c "
import json, sys; r = json.load(sys.stdin)
if 'error' in r: print('ERROR', r['error']); sys.exit(1)
print('status', r.get('status'))
for o in r.get('output', []): print(' -', o.get('type'), o.get('name', ''), repr((o.get('input') or (o.get('content') or [{}])[0].get('text', '')))[:200])"
