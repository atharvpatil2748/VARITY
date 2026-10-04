// VERITY Cline SDK bridge (contract 10; owner Atharv).
//
// One process per chat conversation. Newline-delimited JSON over stdio:
//   -> {"type":"init","systemPrompt":"...","providerId":"...","modelId":"..."}
//   -> {"type":"run"|"continue","text":"..."}
//   <- {"text":"<agent answer>"}
//
// The four canonical tools (names/schemas identical to contract 09) call the
// Python VerityService ONLY through the loopback HTTP API (contract 11).
// This bridge never opens SQLite and never reads source files directly.
// The @cline/sdk version is pinned in package.json (contract 10 requires a
// pinned version + type-checked smoke).

import { Agent, createTool } from "@cline/sdk";
import readline from "node:readline";

const API_BASE = process.env.VERITY_API_BASE ?? "http://127.0.0.1:8765";

async function callApi(path, options) {
  const res = await fetch(API_BASE + path, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  return res.json();
}

const tools = [
  createTool({
    name: "search_evidence",
    description:
      "Hybrid evidence search across the knowledge space. Call this before " +
      "any factual claim. Returns a SearchResult of citable Evidence.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      required: ["query"],
      properties: {
        query: { type: "string", minLength: 2, maxLength: 2000 },
        document_ids: { type: ["array", "null"], items: { type: "string", format: "uuid" } },
        document_kinds: { type: ["array", "null"], items: { type: "string", enum: ["spec", "general"] } },
        chunk_kinds: { type: ["array", "null"], items: { type: "string", enum: ["requirement", "acceptance_criterion", "api_definition", "general_chunk", "code_chunk"] } },
        limit: { type: "integer", minimum: 1, maximum: 20, default: 8 },
        per_document_limit: { type: ["integer", "null"], minimum: 1, maximum: 20, default: null },
      },
    },
    execute: (args) => callApi("/api/v1/search", { method: "POST", body: JSON.stringify(args) }),
  }),
  createTool({
    name: "get_requirement",
    description: "Resolve one explicit spec requirement by its req_ id.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      required: ["requirement_id"],
      properties: { requirement_id: { type: "string", pattern: "^req_[0-9a-f]{64}$" } },
    },
    execute: (args) => callApi(`/api/v1/requirements/${args.requirement_id}`),
  }),
  createTool({
    name: "get_evidence",
    description: "Resolve one evidence id to its exact quote, locator and context.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      required: ["evidence_id"],
      properties: {
        evidence_id: { type: "string", pattern: "^ev_[0-9a-f]{64}$" },
        context_chars: { type: "integer", minimum: 0, maximum: 4000, default: 1000 },
      },
    },
    execute: (args) =>
      callApi(`/api/v1/evidence/${args.evidence_id}?context_chars=${args.context_chars ?? 1000}`),
  }),
  createTool({
    name: "check_coverage",
    description:
      "Inspect the configured workspace for requirement coverage. The only " +
      "coverage statement; never claim coverage from your own edits.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      required: ["requirement_ids", "workspace_id"],
      properties: {
        requirement_ids: { type: "array", minItems: 1, maxItems: 50, uniqueItems: true, items: { type: "string", pattern: "^req_[0-9a-f]{64}$" } },
        workspace_id: { type: "string", pattern: "^[a-z][a-z0-9_-]{0,31}$" },
        run_tests: { type: "boolean", default: false },
      },
    },
    execute: (args) => callApi("/api/v1/coverage", { method: "POST", body: JSON.stringify(args) }),
  }),
];

const rl = readline.createInterface({ input: process.stdin });
let agent = null;

function reply(payload) {
  process.stdout.write(JSON.stringify(payload) + "\n");
}

rl.on("line", (line) => {
  if (!line.trim()) return;
  const msg = JSON.parse(line);
  if (msg.type === "init") {
    // Contract 10: `new Agent({providerId, modelId, systemPrompt, tools})`.
    agent = new Agent({
      providerId: msg.providerId,
      modelId: msg.modelId,
      systemPrompt: msg.systemPrompt,
      tools,
    });
    reply({ ok: true });
  } else if (msg.type === "run") {
    agent.run(msg.text).then((result) => reply({ text: result.text }));
  } else if (msg.type === "continue") {
    agent.continue(msg.text).then((result) => reply({ text: result.text }));
  } else {
    reply({ error: "unknown message type" });
  }
});