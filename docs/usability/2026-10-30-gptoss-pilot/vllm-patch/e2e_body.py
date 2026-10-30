"""The request bodies of the two e2e tests, as JSON on stdout: `single` (one custom-tool
call expected back) or `roundtrip` (the call and its output as request input). MODEL_NAME from
the environment (default gpt-oss-20b)."""
import json
import os
import sys

TOOL = {"type": "custom", "name": "apply_patch",
        "description": "Apply a patch in the *** Begin Patch / *** End Patch format. The input is the patch text.",
        "format": {"type": "text"}}
PATCH = "*** Begin Patch\n*** Add File: hello.txt\n+hi\n*** End Patch"
model = os.environ.get("MODEL_NAME", "gpt-oss-20b")
if sys.argv[1] == "single":
    body = {"model": model, "input": "Use the apply_patch tool to add a file hello.txt containing the line hi. Call the tool now.",
            "tools": [TOOL], "reasoning": {"effort": "low"}, "max_output_tokens": 300}
elif sys.argv[1] == "roundtrip":
    body = {"model": model, "input": [
        {"type": "message", "role": "user", "content": "Add a file hello.txt containing the line hi, using the apply_patch tool, then tell me in one sentence what you did."},
        {"type": "custom_tool_call", "call_id": "call_test1", "name": "apply_patch", "input": PATCH},
        {"type": "custom_tool_call_output", "call_id": "call_test1", "output": "Success. Updated the following files:\nA hello.txt"}],
        "tools": [TOOL], "reasoning": {"effort": "low"}, "max_output_tokens": 200}
else:
    sys.exit("e2e_body.py single|roundtrip")
print(json.dumps(body))
