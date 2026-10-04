/** VERITY typed API mock client (U1, owner Vanashree).
 *
 * Contract 11: base URL http://127.0.0.1:8765/api/v1. This mock serves
 * frozen fixture JSON that validates against contract 21 machine
 * schemas (enforced by tests/test_ui_fixtures.py). It never fabricates
 * statuses or retrieval logic; error/loading states surface the same
 * canonical HttpError shape the real API returns.
 *
 * Usage: const api = new MockApiClient(); api.getHealth().then(...)
 * Switch to the real API later (U6, after PR-V3) by replacing this
 * module with a fetch-based client exposing identical methods.
 */

const FIXTURES = {
  health: "./fixtures/health.json",
  documents: "./fixtures/documents.json",
  search: "./fixtures/search.json",
  coverage: "./fixtures/coverage.json",
  evidence: "./fixtures/evidence.json",
  errorInvalidRequest: "./fixtures/error_invalid_request.json",
};

export class ApiError extends Error {
  /** @param {{error: {code: string, message: string, request_id: string}}} body */
  constructor(body) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.requestId = body.error.request_id;
    this.body = body;
  }
}

export class MockApiClient {
  constructor({ latencyMs = 120 } = {}) {
    this.latencyMs = latencyMs;
    this._cache = new Map();
    this._failNext = null;
  }

  /** Make the next call reject with the given fixture (error injection). */
  failNext(fixtureName) {
    this._failNext = fixtureName;
  }

  async _load(name) {
    if (this._failNext) {
      const failing = this._failNext;
      this._failNext = null;
      const body = await this._fetch(failing);
      throw new ApiError(body);
    }
    return this._fetch(name);
  }

  async _fetch(name) {
    if (!this._cache.has(name)) {
      const response = await fetch(FIXTURES[name]);
      if (!response.ok) {
        throw new Error(`fixture ${name} could not be loaded`);
      }
      this._cache.set(name, await response.json());
    }
    await new Promise((r) => setTimeout(r, this.latencyMs));
    return structuredClone(this._cache.get(name));
  }

  /** GET /health -> Health */
  async getHealth() { return this._load("health"); }

  /** GET /documents -> ListPage<Document> */
  async listDocuments() { return this._load("documents"); }

  /** POST /search -> SearchResult (mock ignores the request body) */
  async search() { return this._load("search"); }

  /** POST /coverage -> CoverageResult */
  async checkCoverage() { return this._load("coverage"); }

  /** GET /coverage/{id} -> CoverageResult */
  async getCoverage() { return this._load("coverage"); }

  /** GET /evidence/{id} -> EvidenceLookup (score is null on direct lookup) */
  async getEvidence() { return this._load("evidence"); }
}

export const api = new MockApiClient();
