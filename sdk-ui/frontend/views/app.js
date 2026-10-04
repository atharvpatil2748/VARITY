/** VERITY UI router (owner Vanashree). U2–U5 views over the typed client.
 *
 * U6 real switch: add ?api=real to the URL to swap the mock client for
 * the real /api/v1 client (contract 11); default remains the offline
 * mock so the static demo works without a backend.
 */

import { MockApiClient } from "../api-mock/client.js";
import { RealApiClient } from "../api-client.js";
import { documentsView, sourcesView, uploadView } from "./documents.js";
import { searchView, evidenceView } from "./search.js";
import { coverageView } from "./coverage.js";
import { chatView } from "./chat.js";
import { loadingState } from "./helpers.js";

const outlet = document.getElementById("view");

const useRealApi = new URLSearchParams(window.location.search).get("api") === "real";
export const api = useRealApi
  ? new RealApiClient()
  : new MockApiClient();

const routes = {
  documents: async () => documentsView(api),
  sources: async () => sourcesView(api),
  search: async () => searchView(api, openEvidence),
  coverage: async () => coverageView(api),
  chat: async () => chatView(api),
};

let uploadPanel = null;
function showUpload() {
  if (!uploadPanel) {
    uploadPanel = uploadView(api, () => navigate("documents"));
  }
  outlet.replaceChildren(uploadPanel);
}

function openEvidence(evidenceId) {
  outlet.replaceChildren(loadingState());
  evidenceView(api, evidenceId, () => navigate("search")).then((view) => {
    if (outlet.firstChild && outlet.firstChild.className === "loading-state") {
      outlet.replaceChildren(view);
    }
  });
}

async function navigate(name) {
  if (name === "upload") return showUpload();
  outlet.replaceChildren(loadingState());
  const view = await routes[name]();
  outlet.replaceChildren(view);
}

document.querySelectorAll("nav a").forEach((a) =>
  a.addEventListener("click", (event) => {
    event.preventDefault();
    navigate(a.dataset.view);
  }));

navigate("documents");
