# Team ownership and merge plan

**Owner:** Atharv for coordination. **Consumers:** all four developers. The table is the code and contract ownership matrix. Ownership gives one person final edit responsibility for shared files; consumers review contract changes.

| Contract / module | Owner | Consumers |
|---|---|---|
| `01`, `02`, `03`, `13`, `14`, `15`, `16`, `17`, `20`; `verity/models.py`, `ids.py`, `errors.py`, `config.py`, `storage/*`, `evidence.py`, `service.py` | Atharv Patil | All |
| `04`, `05`, `06`, `08`; `verity/ingestion/*`, `verity/retrieval/*` | Piyush Ghayal | Atharv, Vandit, Vanashree |
| `09`, `11`, `18`; `verity/mcp/*`, `verity/http/*`, transport contract harness | Vandit Gupta | Atharv, Piyush, Vanashree, UI |
| `12`; `verity/coverage/*`, UI presentation under `sdk-ui/frontend/*`, coverage demo fixture | Vanashree | Atharv, Vandit, Piyush |
| `07`, `10`; SDK gateway/tool adapter under `sdk-ui/gateway/*` | Atharv Patil | Vanashree, Vandit |

Shared/rarely modified after freeze: `Docs/contracts/*`, `verity/models.py`, `ids.py`, `errors.py`, `config.py`, `verity/service.py`, DB migration files and shared golden fixtures. Owner-modified: ingestion/retrieval by Piyush, MCP/HTTP by Vandit, coverage/frontend by Vanashree, persistence/evidence/SDK gateway by Atharv. No owner creates parallel DTOs for shared concepts. A consumer needing a field change proposes it under `02` and waits for the model owner to update contract and golden fixture first.

Recommended Git workflow: each owner works on a branch touching primarily owned directories; use small commits and integrate at hours 1, 3 and 5. Merge model/schema changes first, then producers, then adapters/UI. Do not have four branches edit `service.py` simultaneously; Atharv maintains composition and supplies stable stubs/interfaces at hour 1. Use a single integration branch with one merger at checkpoints. Resolve conflicts by contract documents, not by whichever implementation landed first. Do not copy Mnemo's proprietary code into VERITY without a separate rights decision.
