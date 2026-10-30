#!/bin/sh
# Run inside the vLLM container (vllm/vllm-openai:v0.32.0): copies the six patched files over the installed ones.
# Source: ~/vllm-patch/ (this directory). The patch lets gpt-oss's harmony path accept custom (free-form) tools:
# a custom tool is shown to the model as vLLM's single-string function shim and its call comes back as a
# custom_tool_call item with the payload unwrapped (both the streaming and the non-streaming Responses path), and an
# earlier custom_tool_call / custom_tool_call_output in the request input is replayed to the model as that shim call.
set -e
D=$(dirname "$0")
dest() { python3 -c "import importlib; print(importlib.import_module('$1').__file__)"; }
cp "$D/harmony_utils.py"     "$(dest vllm.entrypoints.openai.parser.harmony_utils)"
cp "$D/responses_utils.py"   "$(dest vllm.entrypoints.openai.responses.utils)"
cp "$D/harmony.py"           "$(dest vllm.entrypoints.openai.responses.harmony)"
cp "$D/streaming_events.py"  "$(dest vllm.entrypoints.openai.responses.streaming_events)"
cp "$D/serving.py"           "$(dest vllm.entrypoints.openai.responses.serving)"
cp "$D/online_renderer.py"   "$(dest vllm.renderers.online_renderer)"
python3 -c "import vllm.entrypoints.openai.responses.serving, vllm.entrypoints.openai.responses.streaming_events, vllm.entrypoints.openai.responses.harmony, vllm.renderers.online_renderer; print('vllm custom-tool patch installed, imports ok')"
