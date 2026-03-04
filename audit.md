# Codebase Audit Dimensions

When auditing or reviewing a refactor, all 8 dimensions below must be explicitly checked. The first-round audit of this codebase only checked dimension 1 (referential integrity), which missed 25 runtime robustness issues that were caught in the second round.

## 1. Referential Integrity

Do all references resolve? Every file path, module import, function call, config key, env var reference, and cross-file dependency must point to something that exists.

- Do imported modules exist?
- Do referenced file paths resolve?
- Do config keys match what the code expects?
- Do workflow step references (actions, scripts) resolve?

## 2. Failure Mode Analysis

What happens when operations fail? Every I/O operation, API call, and external dependency can fail. Trace the failure path.

- What happens if an API call returns an error?
- What happens if a file read/write fails mid-operation?
- Do errors propagate clearly or get swallowed silently?
- Are error messages descriptive enough to diagnose the problem?

## 3. Data Atomicity

Are writes crash-safe? Any operation that writes data must be resilient to process crashes, power loss, or OOM kills happening mid-write.

- Do full-file rewrites use atomic patterns (temp file + rename)?
- Can a crash during write corrupt or truncate existing data?
- Are cumulative data stores (logs, metrics) protected against partial writes?
- Is append-only I/O used where appropriate?

## 4. Concurrency Safety

What happens when operations run simultaneously? CI workflows, cron jobs, and manual triggers can overlap.

- Do concurrent workflows share the same concurrency group?
- Can two processes write to the same file at the same time?
- Do push/commit operations handle concurrent pushes (rebase, retry)?
- Are rate limits respected when multiple callers hit the same API?

## 5. Input Validation

Are missing, empty, null, and wrong-type inputs handled? Every function that receives external data (API responses, file contents, user inputs) must validate before using.

- Are dict keys accessed with `.get()` instead of `[]` for external data?
- Are None/empty checks performed before passing values downstream?
- Are type assumptions verified (e.g., expecting list but getting int)?
- Do API response parsers validate structure before nested key access?

## 6. Error Propagation

Do errors surface clearly or get swallowed? The right errors must reach the right handlers — not silently disappear and not crash unrelated operations.

- Do non-critical failures (e.g., Slack notifications) avoid crashing the pipeline?
- Do critical failures (e.g., data writes) raise and propagate?
- After retry exhaustion, is an explicit error raised (not silent fallthrough)?
- Are error messages specific enough to identify the failing component and context?

## 7. Configuration Completeness

Are all env vars, secrets, and config values provided and validated where needed?

- Does every workflow that calls a Python module provide all env vars that module reads?
- Are env vars validated at startup (fail fast) rather than at first use (fail late)?
- Are defaults sensible, and is the absence of optional config logged?
- Do all environments (CI, local dev) have access to required config?

## 8. Idempotency

Can operations be safely retried? Workflows fail and get re-run. Steps crash and restart. Every operation should produce the same result whether run once or multiple times.

- Do posting operations check for already-posted state before re-posting?
- Do file writes produce the same result on re-run?
- Do API calls handle "already exists" responses gracefully?
- Can a partially completed workflow be safely re-triggered?

---

## Applying These Dimensions

When reviewing code, explicitly prompt for each dimension. A checklist:

```
[ ] 1. Referential integrity — all references resolve
[ ] 2. Failure modes — all I/O failures handled
[ ] 3. Data atomicity — all writes are crash-safe
[ ] 4. Concurrency — no race conditions
[ ] 5. Input validation — no unvalidated external data
[ ] 6. Error propagation — errors surface correctly
[ ] 7. Configuration — all env vars provided
[ ] 8. Idempotency — operations safe to retry
```

The first audit round only checked box 1. The second round found 25 issues across boxes 2-7.
