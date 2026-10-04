/** U4: Coverage view (contracts 11/12, owner Vanashree).
 * Renders CoverageResult verbatim: status, reason, code/test evidence
 * spans and limitations. The UI never calculates a status; UNCERTAIN is
 * always visible with its honest reason (contract 12).
 */

import { el, esc, emptyState, errorCard, loadingState } from "./helpers.js";

function spanBlock(title, spans) {
  if (!spans || spans.length === 0) return null;
  return el("details", { class: "spans" },
    el("summary", {}, `${title} (${spans.length})`),
    ...spans.map((s) => el("div", { class: "span-item" },
      el("code", {}, `${esc(s.path)}:${s.start_line}â€“${s.end_line}`),
      el("div", { class: "muted" },
        `basis ${esc(s.basis)}${s.outcome ? `, outcome ${esc(s.outcome)}` : ""}`),
      el("pre", {}, s.excerpt))));
}

function coverageRow(row) {
  return el("li", { class: "card coverage-card" },
    el("div", { class: "coverage-head" },
      el("span", { class: `status-pill ${esc(row.status)}` }, esc(row.status)),
      el("code", {}, esc(row.requirement_id.slice(0, 20)) + "â€¦")),
    el("p", {}, esc(row.reason)),
    spanBlock("Implementation evidence", row.implementation),
    spanBlock("Test evidence", row.tests),
    row.limitations && row.limitations.length > 0
      ? el("ul", { class: "warnings" },
          ...row.limitations.map((l) => el("li", {}, esc(l))))
      : null);
}

export function coverageView(api) {
  const ids = el("input", {
    type: "text",
    placeholder: "requirement IDs (comma-separated, e.g. req_abc...)",
    style: "min-width:420px" });
  const run = el("button", { type: "submit" }, "Check");
  const form = el("form", { class: "search-form" }, ids, run);
  const results = el("div", {},
    emptyState("Enter requirement IDs and click Check."));

  async function check(idList) {
    results.replaceChildren(loadingState());
    try {
      const report = await api.checkCoverage(idList, "demo", false);
      results.replaceChildren(
        el("small", { class: "muted" },
          `workspace ${esc(report.workspace_id)}, ` +
          `revision ${esc(report.workspace_revision.slice(0, 12))}..., ` +
          `inspected ${esc(report.inspected_at)}`),
        report.results.length === 0
          ? emptyState("No coverage results in this run.")
          : el("ul", { class: "card-list" },
              ...report.results.map(coverageRow)),
        report.limitations && report.limitations.length > 0
          ? el("ul", { class: "warnings" },
              ...report.limitations.map((l) => el("li", {}, esc(l))))
          : null);
    } catch (e) {
      results.replaceChildren(errorCard(e.body ?? e));
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const idList = ids.value.split(",").map((s) => s.trim()).filter(Boolean);
    check(idList);
  });
  return el("div", {}, el("h2", {}, "Coverage"), form, results);
}