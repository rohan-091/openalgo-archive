# Antigravity & Agent Guidelines

## 🛑 STRICT UPSTREAM RESTRICTIONS
1. **NEVER create Pull Requests to upstream (`marketcalls/openalgo`)**:
   - Under no circumstances should any Pull Request or merge request be opened against the upstream repository `marketcalls/openalgo`.
2. **NEVER push to upstream**:
   - The `upstream` remote is strictly read-only for fetching updates.
   - The push URL for `upstream` is permanently set to `DISABLE`.
3. **Repository Scope**:
   - All branches, commits, PRs, and pushes must be made **exclusively** to the user's personal repository:
     `origin` (`https://github.com/rohan-091/openalgo.git`).

---

## 🔒 CREDENTIALS & PRIVACY SAFEGUARDS
- Never commit `.env`, `*.db`, SQLite files, user credentials, broker secrets, or password hashes.
- Never commit active trade state files (`trading_agent/active_trades_state.json`) or personal trade journals (`TRADES.md`).
- Always keep all trading execution in OpenAlgo **Analyzer mode** (paper trading) unless the user explicitly and repeatedly requests live broker deployment.
