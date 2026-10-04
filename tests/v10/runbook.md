# V10 runbook — external Cline client proof (PR-V4 evidence)

Goal (roadmap 04, V10): a recorded session where a real external Cline
client calls the four frozen VERITY tools through `python -m verity.mcp`
and cites `[[ev_<64hex>]]` markers, plus the restart proof. Two evidence
tracks, per the team decision: (1) the scripted, CI-reproducible trace, and
(2) the recorded Cline Desktop session.

## Track 1 — scripted proof (automated, already green in CI)

```
python -m pytest tests/test_v10_external_client.py -q -s
```

This spawns the production entrypoint as a real stdio subprocess, drives
all four tools, prints the recorded trace (server version, four tool names,
cited evidence/requirement IDs, citation label, coverage run) and proves
the restart: server #2 resolves the same cited evidence byte-identically.
Save the output with the PR-V4 record.

## Track 2 — recorded Cline Desktop session

### One-time setup
1. Install Cline Desktop (Windows beta): https://cline.bot/desktop
   (the VS Code extension works identically with the same config).
2. Seed the demo (idempotent; repo-root cwd):
   `python tests/v10/seed_demo.py`
   It creates `demo-workspace/src/refund.py` + `tests/test_refund.py`
   (the REQ-001 implementation) and ingests `payments.md` through the
   real service; it prints the seeded evidence IDs.
3. Register the VERITY MCP server: merge `tests/v10/cline_mcp_settings.json`
   into `~/.cline/data/settings/cline_mcp_settings.json` (adjust `cwd` if
   your repo path differs). The four VERITY tools are auto-approved.

### Recorded session (what to capture)
Ask the agent, in one conversation:
1. "Search the payments spec for the refund window policy." →
   agent calls `search_evidence` → capture the tool call + the
   `ev_...` citation in its answer.
2. "What exactly does REQ-001 require?" → `get_requirement`.
3. "Show me the provenance of the evidence you cited." → `get_evidence`.
4. "Check whether the demo workspace implements the refund window
   requirement." → `check_coverage`. With PR-N2 merged the real candidate
   search runs, so report the status the tool actually returns — record it
   honestly, never "fix" it to a nicer value.
5. Restart proof: close the Cline session (server process exits), reopen
   and ask "resolve the evidence you cited before" → the same `ev_` ID
   resolves identically from the persisted DB.

### What the PR-V4 record must contain
- The Desktop session transcript (tool calls + cited `[[ev_...]]` markers).
- The Track 1 scripted trace output.
- The restart before/after evidence payloads (byte-identical).
- Commit hash of the merged PR-V3 the server ran against.

## Honest-state notes
- Record the `retrieval_mode` the tool actually reports — do not label the
  result hybrid unless the payload says so. (PR-P3/#12 was superseded by the
  merged PR-P4/#15 retrieval work.)
- With PR-N2 (#18) merged, coverage runs the real candidate search: report
  whatever status comes back (IMPLEMENTED / MISSING / UNCERTAIN) per contract
  12 — the statuses stay honest by construction.
- `python -m verity.mcp` never substitutes a fake; it exits if the real
  service is unavailable.