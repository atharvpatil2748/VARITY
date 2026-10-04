# VERITY Cline integration demo addendum

**Applies to:** [VERITY_Cline_Hackathon_Round1_v2.pptx](VERITY_Cline_Hackathon_Round1_v2.pptx), especially slides 5–7 and 9. **Status:** current presenter guidance, 2026-10-04. The PPTX records the original Round 1 pitch and remains unchanged; [contract index](../contracts/01_VERITY_CONTRACT_INDEX.md) and [SDK contract](../contracts/10_VERITY_CLINE_SDK_CONTRACT.md) govern implementation.

## Current architecture to say in the demo

**Cline SDK powers our native VERITY agent UI; MCP exposes VERITY to external Cline clients.** Both integrations call the same `VerityService` and receive canonical requirements, retrieval results, Evidence, citations and coverage. The native UI calls the frozen chat API, whose handler delegates to the Cline SDK gateway. The SDK agent reasons and returns an answer with resolved Evidence; the UI renders it. External Cline connects to VERITY's MCP server. Neither integration has its own retrieval engine or Evidence format.

```text
Native:   VERITY UI → /api/v1/chat → Cline SDK agent → canonical tools → VerityService
External: Cline client → VERITY MCP server ───────────────────────────→ VerityService
Core:     VerityService → retrieval / Evidence / requirements / coverage
```

## How to present the original slides

| Original slide | Presenter correction |
|---|---|
| 5, core features | The frozen MCP v1 surface has exactly `search_evidence`, `get_requirement`, `get_evidence`, `check_coverage`. The deck predates the final four-tool freeze. |
| 6, architecture | Read “Cline / VS Code / CLI” as an **external Cline client** using MCP. Read “SDK agent + React UI” as the architecture of **native VERITY chat**. Its implementation was scheduled later in the original eight-hour pitch; it is not an alternate native agent path. Do not demo `compare_sources` as an MCP tool. |
| 7, Cline integration | The deck's “primary” and “stretch” labels describe the original delivery order, not the current client architecture. State the native SDK versus external MCP distinction above. Both converge on `VerityService`. |
| 9, eight-hour plan | The backend/external MCP demo may be completed before native SDK chat. If the SDK path is not implemented and tested, say native chat is unavailable; do not show a mock or non-Cline response as a working native UI. |

## Demo proof

For the external-client proof, show a real Cline MCP call, returned canonical Evidence and coverage. For the native UI proof, show a real Cline SDK agent response through `/api/v1/chat/*` with resolved Evidence rendered by the UI. Use the same source/evidence identities in both paths. If only the backend/MCP baseline is ready, present that result accurately and list native SDK chat as unfinished sprint work. The original PPTX is kept as a historical artifact; this addendum is the current narration until a separately reviewed deck revision is produced.
