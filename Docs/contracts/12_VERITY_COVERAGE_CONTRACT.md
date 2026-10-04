# Workspace coverage contract

**Owner:** Vanashree. **Consumers:** Atharv service, Vandit MCP/API, UI. **Version:** 1.0.0. Coverage is an observed workspace scan, never a mutable status database. `CoverageRequest = {requirement_ids: req-hash[], workspace_id: config key, run_tests: boolean}`. All fields required on the canonical model; adapters apply defaults (`run_tests=false`). IDs are unique, 1–50, and preserve request order. The result is `CoverageResult` from `03` with one `RequirementCoverage` per requested ID.

```text
MCP/API/SDK -> VerityService.check_coverage
             -> CoverageService
             -> WorkspaceScanner (safe snapshot)
             -> CodeEvidenceRetriever (candidate spans)
             -> RequirementEvaluator (status + reason)
             -> immutable CoverageResult store
```

Only `WorkspaceScanner` opens workspace files. It resolves the configured absolute root for `workspace_id`, rejects missing roots and paths escaping through symlinks, ignores `.git`, virtual environments, dependencies, binaries and configured excludes, caps file size at 1 MiB and total scan at 5,000 files. It hashes the sorted relative-path/content-hash manifest as `workspace_revision`, before and after evaluation; if changed, the run is `COVERAGE_UNAVAILABLE` or all affected items `UNCERTAIN` with `workspace_changed`, never a confident result. Candidate search may use `rg`, FTS or AST internally. It returns bounded `CodeEvidence` and `TestEvidence` with exact relative path and line span. The evaluator receives the exact active `Requirement`, linked acceptance criteria and these candidates; it does not accept a caller's status claim.

`IMPLEMENTED`: relevant implementation spans support every essential normative clause and acceptance criterion, with test evidence or a documented static proof for each; if tests were requested, relevant executed tests passed. `PARTIAL`: credible implementation exists but some clause/criterion or test support is missing. `MISSING`: scan completed for supported language/files with no credible implementation span. `UNCERTAIN`: ambiguous behavior, unsupported language, incomplete/changed scan, inaccessible files, failed test runner, or insufficient evidence to distinguish missing from hidden. A comment containing `REQ-001` alone is never implementation evidence. No tests with credible implementation usually means `PARTIAL`; no analyzable code means `UNCERTAIN`, not `MISSING`. A failing relevant test yields `PARTIAL` or `UNCERTAIN` with its `TestOutcome=failed`, never `IMPLEMENTED`.

Tests are never run by an arbitrary MCP-supplied command. `run_tests=true` invokes only the allowlisted command for that configured workspace, with 20-second timeout and no network expectation. Test output is bounded, captured as evidence only when it can be mapped to a test file/line, and is never silently treated as proof for an unrelated requirement. `CodeEvidence` and `TestEvidence` schemas, `CoverageStatus` and `TestOutcome` are in `03`. The CoverageService writes one immutable report row after evaluation; a subsequent scan creates a new `coverage_id`. It must not edit code or tests. Total coverage deadline is 30 seconds. Errors use `17`.

Public function boundaries are in `16`: scanner produces `WorkspaceSnapshot`; retriever returns `(CodeEvidence[], TestEvidence[])` keyed by requirement; evaluator returns `RequirementCoverage`; coverage service returns `CoverageResult`. Private search/AST/evaluator heuristics remain flexible. Shared fixture must deliberately contain a requirement ID only in a comment, one implemented condition without a test, one passing test, and one unsupported file so statuses are tested against real files.
