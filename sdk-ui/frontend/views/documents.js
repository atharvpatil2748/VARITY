/** U2: Documents, Sources and Upload views (contract 11, owner Vanashree).
 * Renders ListPage<Document>/ListPage<Source> offsets, document status,
 * metadata warnings and IngestResult (201 new / 200 same bytes).
 */

import { el, esc, emptyState, errorCard, loadingState } from "./helpers.js";

function statusBadge(status) {
  return el("span", { class: `status-pill status-${esc(status)}` }, status);
}

function warningsBlock(metadata) {
  if (!metadata || !metadata.warnings || metadata.warnings.length === 0) {
    return null;
  }
  return el("ul", { class: "warnings" },
    ...metadata.warnings.map((w) => el("li", {}, esc(w))));
}

function documentRow(doc) {
  return el("li", { class: "card document-card" },
    el("div", { class: "document-head" },
      el("strong", {}, esc(doc.name)),
      statusBadge(doc.status),
      el("span", { class: "kind" }, esc(doc.kind))),
    el("small", {},
      `${esc(doc.media_type)} — version ${esc(doc.version_id.slice(0, 8))}… ` +
      `— indexed ${esc(doc.indexed_at)}`),
    doc.metadata && doc.metadata.title
      ? el("small", { class: "muted" }, esc(doc.metadata.title))
      : null,
    warningsBlock(doc.metadata));
}

export async function documentsView(api) {
  const root = el("div", {}, loadingState());
  try {
    const page = await api.listDocuments();
    root.replaceChildren(
      el("h2", {}, "Documents"),
      el("small", { class: "muted" },
        `${page.items.length} of ${page.total} (limit ${page.limit}, offset ${page.offset})`),
      page.items.length === 0
        ? emptyState("No documents indexed yet.")
        : el("ul", { class: "card-list" }, ...page.items.map(documentRow)));
  } catch (e) {
    root.replaceChildren(el("h2", {}, "Documents"), errorCard(e.body ?? e));
  }
  return root;
}

function sourceRow(source) {
  return el("li", { class: "card source-card" },
    el("strong", {}, esc(source.source_path)),
    el("small", {},
      source.source_key ? `key: ${esc(source.source_key)}` : "no source key"),
    el("small", { class: "muted" }, `registered ${esc(source.registered_at)}`));
}

export async function sourcesView(api) {
  const root = el("div", {}, loadingState());
  try {
    const page = await api.listSources();
    root.replaceChildren(
      el("h2", {}, "Sources"),
      el("small", { class: "muted" }, `total ${page.total}`),
      page.items.length === 0
        ? emptyState("No sources registered.")
        : el("ul", { class: "card-list" }, ...page.items.map(sourceRow)));
  } catch (e) {
    root.replaceChildren(el("h2", {}, "Sources"), errorCard(e.body ?? e));
  }
  return root;
}

export function uploadView(api, onUploaded) {
  const mode = el("select", {},
    el("option", { value: "auto" }, "auto"),
    el("option", { value: "spec" }, "spec"),
    el("option", { value: "general" }, "general"));
  const file = el("input", { type: "file", required: "" });
  const feedback = el("div", { class: "upload-feedback" });
  const form = el("form", { class: "card upload-form" },
    el("h2", {}, "Upload document"),
    file,
    el("label", {}, "mode ", mode),
    el("button", { type: "submit" }, "Upload"),
    feedback);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    feedback.replaceChildren(loadingState());
    try {
      const result = await api.uploadDocument();
      feedback.replaceChildren(el("div", { class: "upload-ok" },
        el("strong", {}, result.created_new_version
          ? "201 — new source/version created"
          : "200 — same bytes, existing version returned"),
        el("div", {},
          `${esc(result.document.name)} — status ${esc(result.document.status)}`)));
      onUploaded?.();
    } catch (e) {
      feedback.replaceChildren(errorCard(e.body ?? e));
    }
  });
  return form;
}
