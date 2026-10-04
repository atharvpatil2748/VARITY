/** Shared DOM helpers for VERITY UI views (owner Vanashree). */

export function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2), value);
    } else node.setAttribute(key, value);
  }
  for (const child of children) {
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

export const esc = (text) =>
  String(text).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

/** Canonical HTTP error card (contract 17 Error via HttpError). */
export function errorCard(error) {
  return el("div", { class: "card error-card" },
    el("strong", {}, `Error ${error.code}`),
    el("div", {}, error.message),
    el("small", {}, `request ${error.requestId}`));
}

export function emptyState(message) {
  return el("div", { class: "empty-state" }, el("em", {}, message));
}

export function loadingState() {
  return el("div", { class: "loading-state" },
    el("div", { class: "sk" }),
    el("div", { class: "sk" }),
    el("div", { class: "sk" }));
}
