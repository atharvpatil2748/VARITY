/** U5: Native Cline SDK chat presentation (contracts 10/11, owner Vanashree).
 *
 * The UI renders the SDK agent's answer and its resolved Evidence only —
 * no UI retrieval, no second agent, no status calculation. Citation
 * markers in the answer must match returned evidence IDs; anything
 * unresolved is flagged honestly. SDK absence is a truthful 503
 * SDK_UNAVAILABLE card, never a substituted answer.
 */

import { el, esc, emptyState, errorCard, loadingState } from "./helpers.js";

function evidenceChip(ev) {
  return el("li", { class: "card evidence-chip" },
    el("strong", {}, esc(ev.citation.label)),
    el("blockquote", {}, esc(ev.quote)),
    el("small", { class: "muted" }, esc(ev.citation.locator.source_path)));
}

function assistantMessage(response) {
  const resolved = new Map(response.evidence.map((ev) => [ev.evidence_id, ev]));
  const cited = response.message.citations || [];
  const unresolved = cited.filter((id) => !resolved.has(id));
  return el("div", { class: "card chat-message" },
    el("div", { class: "muted" }, `assistant — ${esc(response.message.created_at)}`),
    el("p", {}, esc(response.message.text)),
    cited.length > 0
      ? el("ul", { class: "card-list" },
          ...cited.filter((id) => resolved.has(id))
                  .map((id) => evidenceChip(resolved.get(id))))
      : emptyState("The answer cited no evidence."),
    unresolved.length > 0
      ? el("div", { class: "warnings" },
          `unresolved citation markers: ${unresolved.map(esc).join(", ")}`)
      : null);
}

export function chatView(api) {
  const transcript = el("div", { class: "transcript" },
    emptyState("Start a session to talk to the Cline SDK agent."));
  const input = el("input", {
    type: "text", placeholder: "Ask using the evidence…",
    minlength: "1", maxlength: "8000", disabled: "" });
  const send = el("button", { type: "submit", disabled: "" }, "Send");
  const status = el("small", { class: "muted" }, "no session — create one first");
  let sessionId = null;

  const form = el("form", { class: "chat-form" }, input, send);
  const root = el("div", {},
    el("h2", {}, "Native chat (Cline SDK)"),
    status,
    el("button", {
      type: "button",
      onclick: async () => {
        status.replaceChildren(loadingState());
        try {
          const session = await api.createChatSession();
          sessionId = session.session_id;
          status.textContent =
            `session ${sessionId.slice(0, 8)}… created ${session.created_at}`;
          input.disabled = false;
          send.disabled = false;
          transcript.replaceChildren(emptyState("Ask anything about the specs."));
        } catch (e) {
          // Contract 11: missing SDK is a truthful 503, not another agent.
          status.textContent = "SDK unavailable";
          transcript.replaceChildren(errorCard(e.body ?? e));
        }
      },
    }, "Start session"),
    transcript,
    form);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || !sessionId) return;
    transcript.append(el("div", { class: "card chat-message user" },
      el("div", { class: "muted" }, "user"),
      el("p", {}, text)));
    transcript.append(loadingState());
    try {
      const response = await api.sendChatMessage();
      transcript.lastChild.replaceWith(assistantMessage(response));
      input.value = "";
    } catch (e) {
      transcript.lastChild.replaceWith(errorCard(e.body ?? e));
    }
  });
  return root;
}