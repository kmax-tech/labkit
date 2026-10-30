# vLLM 0.32.0: custom (free-form) tools on the harmony path

Why: gpt-oss takes vLLM's harmony path, which knew function tools only; Codex CLI
registers `apply_patch` as a custom tool, so every request was refused ("tool type
'custom' is not supported"). The Responses layer already accepted the definition
(grammar formats excepted) and already knew the single-string function shim and
the call-back mapping for custom tools (`tool_parsers/utils.py`,
`responses/utils.py`); the harmony path just did not use them. Found and fixed
layer by layer on 2026-10-30 (pilot contract, addenda 1 to 3).

What (six files; the unified diffs against v0.32.0 are here, `patched/install.sh`
copies the patched files over the installed vLLM inside the running container; the
patched files themselves are vLLM source and live in the internal evidence archive,
`usability/2026-10-30-gptoss-pilot/vllm-patch/patched/`, or come from
`patch -p0 < <file>.diff` on the v0.32.0 sources):

| file | change |
|---|---|
| `parser/harmony_utils.py` | `get_developer_message` shows a custom tool as the shim function (`custom_tool_as_function_dict`) instead of raising |
| `responses/utils.py` | `extract_function_tool_names` counts custom names |
| `responses/harmony.py` | non-streaming: a call to a custom tool returns as `custom_tool_call` with the payload unwrapped; input: `custom_tool_call` / `custom_tool_call_output` items replayed as the shim call and its result |
| `responses/streaming_events.py` | streaming: the same, with `custom_tool_call_input.delta/done` events |
| `responses/serving.py` | hands the request's custom tool names to both paths |
| `renderers/online_renderer.py` | keeps custom calls among the earlier calls, so an output finds its call |

Verified against the running server: `e2e-custom-tool.sh` (single call, both
paths: `custom_tool_call apply_patch "*** Begin Patch … *** End Patch"`) and
`e2e-custom-roundtrip.sh` (second turn with the call and its output as input:
200). The model's behaviour is unchanged: it sees the shim vLLM uses for every
non-harmony model. Not upstreamed; the sandbox's proxy still replaces a grammar
format by the text format, because vLLM refuses grammar formats at acceptance.
