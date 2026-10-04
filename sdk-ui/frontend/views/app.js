/** VERITY UI router (owner Vanashree). U2–U4 views over the typed mock. */

import { api } from "../api-mock/client.js";
import { documentsView, sourcesView, uploadView } from "./documents.js";
import { searchView, evidenceView } from "./search.js";
import { coverageView } from "./coverage.js";
import { chatView } from "./chat.js";
import { loadingState } from "./helpers.js";

const outlet = document.getElementById("view");

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
