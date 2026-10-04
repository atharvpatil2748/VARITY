/** VERITY real API client (U6, owner Vanashree).
 *
 * Same method surface as the mock (api-mock/client.js) so views switch
 * clients without changes. Targets the loopback /api/v1 app (contract
 * 11) served by `verity.http.serve` over the real VerityService. Errors
 * arrive as the canonical HttpError body and surface through ApiError.
 */

export class ApiError extends Error {
  constructor(body) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.requestId = body.error.request_id;
    this.body = body;
  }
}

export class RealApiClient {
  /** @param {string} baseUrl contract-11 base, default loopback */
  constructor({ baseUrl = "http://127.0.0.1:8765/api/v1", latencyMs = 0 } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.latencyMs = latencyMs;
  }

  async _request(path, options = {}) {
    const response = await fetch(this.baseUrl + path, options);
    if (this.latencyMs) {
      await new Promise((r) => setTimeout(r, this.latencyMs));
    }
    const body = await response.json().catch(() => null);
    if (!response.ok || body === null) {
      throw new ApiError(body ?? {
        error: {
          code: "INTERNAL_ERROR",
          message: `unexpected response (${response.status})`,
          request_id: "unknown",
          retryable: true,
        },
      });
    }
    return body;
  }

  /** GET /health -> Health */
  async getHealth() { return this._request("/health"); }

  /** GET /documents -> ListPage<Document> */
  async listDocuments() { return this._request("/documents?limit=50&offset=0"); }

  /** GET /sources -> ListPage<Source> */
  async listSources() { return this._request("/sources?limit=50&offset=0"); }

  /** POST /documents (multipart) -> IngestResult; call site supplies FormData */
  async uploadDocument(form) {
    return this._request("/documents", { method: "POST", body: form });
  }

  /** POST /search -> SearchResult */
  async search(query) {
    return this._request("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query ?? "", document_ids: null, limit: 8 }),
    });
  }

  /** POST /coverage -> CoverageResult */
  async checkCoverage(requirementIds, workspaceId = "demo", runTests = false) {
    return this._request("/coverage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requirement_ids: requirementIds ?? [],
        workspace_id: workspaceId,
        run_tests: runTests,
      }),
    });
  }

  /** GET /coverage/{id} -> stored immutable CoverageResult */
  async getCoverage(coverageId) {
    return this._request(`/coverage/${encodeURIComponent(coverageId)}`);
  }

  /** GET /evidence/{id} -> EvidenceLookup (score null on direct lookup) */
  async getEvidence(evidenceId, contextChars = 1000) {
    return this._request(
      `/evidence/${encodeURIComponent(evidenceId)}?context_chars=${contextChars}`
    );
  }

  /** POST /chat/sessions -> ChatSession (201); 503 SDK_UNAVAILABLE honest */
  async createChatSession() {
    return this._request("/chat/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
  }

  /** POST /chat/sessions/{id}/messages -> ChatResponse */
  async sendChatMessage(sessionId, text) {
    return this._request(`/chat/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  }
}
