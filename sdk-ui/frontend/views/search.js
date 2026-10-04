/** U3: Search and Evidence views (contracts 07/11, owner Vanashree).
 * Renders ranked Evidence cards preserving source/document/page and the
 * canonical citation label; the evidence detail view shows the resolved
 * EvidenceLookup with bounded context and an explicit null score.
 */

import { el, esc, emptyState, errorCard, loadingState } from "./helpers.js";

function locatorSummary(locator) {
  const parts = [];
  if (locator.page !== null) parts.push(`p.${locator.page}`);
  if (locator.start_line !== null) {
    parts.push(`lines ${locator.start_line}–${locator.end_line}`);
  }
  if (locator.heading_path && locator.heading_path.length > 0) {
    parts.push(locator.heading_path.join(" / "));
  }
  return parts.join(", ");
}

function evidenceCard(ev, onOpen) {
  return el("li", { class: "card evidence-card" },
    el("div", { class: "evidence-head" },
      el("strong", {}, esc(ev.citation.label)),
      el("span", { class: "kind" }, esc(ev.kind))),
    el("blockquote", {}, esc(ev.quote)),
    el("small", { class: "muted" }, `${esc(ev.citation.locator.source_path)} — ${locatorSummary(ev.citation.locator)}`),
    ev.requirement_id
      ? el("small", { class: "muted" }, `requirement ${esc(ev.requirement_id.slice(0, 16))}…`)
      : null,
    el("div", { class: "evidence-scores muted" },
      `dense rank ${ev.ranking.dense_rank ?? "—"}, lexical rank ${ev.ranking.lexical_rank ?? "—"}, rrf ${ev.ranking.rrf_score ?? "—"}`),
    el("button", { class: "link", onclick: () => onOpen(ev.evidence_id) },
      "View evidence"));
}

export async function searchView(api, onOpenEvidence) {
  const input = el("input", {
    type: "search", placeholder: "Search evidence…",
    minlength: "2", value: "duplicate refund requests" });
  const results = el("div", {});
  const root = el("div", {},
    el("h2", {}, "Search"),
    el("form", { class: "search-form" }, input, el("button", { type: "submit" }, "Search")),
    results);

  async function run() {
    if (input.value.trim().length < 2) {
      results.replaceChildren(errorCard({
        code: "INVALID_REQUEST",
        message: "query must contain at least two characters",
        requestId: "—",
      }));
      return;
    }
    results.replaceChildren(loadingState());
    try {
      const result = await api.search();
      results.replaceChildren(
        el("small", { class: "muted" },
          `${result.retrieval_mode}, reranker ${result.reranker_used ? "on" : "off"}, ` +
          `${result.completeness}, ${result.items.length} of ${result.total_returned}`),
        result.items.length === 0
          ? emptyState("No evidence matched this query.")
          : el("ul", { class: "card-list" },
              ...result.items.map((ev) => evidenceCard(ev, onOpenEvidence))));
    } catch (e) {
      results.replaceChildren(errorCard(e.body ?? e));
    }
  }

  root.querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
    run();
  });
  await run();
  return root;
}

export async function evidenceView(api, evidenceId, onBack) {
  const root = el("div", {}, loadingState());
  try {
    const lookup = await api.getEvidence();
    const ev = lookup.evidence;
    root.replaceChildren(
      el("h2", {}, "Evidence"),
      el("button", { class: "link", onclick: onBack }, "← back to search"),
      el("div", { class: "card evidence-detail" },
        el("strong", {}, esc(ev.citation.label)),
        el("blockquote", {}, esc(ev.quote)),
        el("small", { class: "muted" },
          `${esc(ev.citation.locator.source_path)} — ${locatorSummary(ev.citation.locator)}`),
        el("small", { class: "muted" },
          `score: null (direct lookup has no query score)`),
        el("h3", {}, "Context"),
        el("pre", {}, lookup.context_before),
        el("blockquote", {}, esc(ev.quote)),
        el("pre", {}, lookup.context_after),
        el("h3", {}, "Provenance"),
        el("small", { class: "muted" },
          `sha256 ${esc(ev.provenance.content_sha256)}, ` +
          `parser ${esc(ev.provenance.parser_name)}@${esc(ev.provenance.parser_version)}, ` +
          `chunker ${esc(ev.provenance.chunker_version)}, ` +
          `model ${esc(ev.provenance.embedding_model ?? "none")}, ` +
          `indexed ${esc(ev.provenance.indexed_at)}`)));
  } catch (e) {
    root.replaceChildren(el("h2", {}, "Evidence"), errorCard(e.body ?? e));
  }
  return root;
}
