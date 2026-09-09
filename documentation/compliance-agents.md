# Compliance Agents

Coverage of the job catalog against NIST titles, plus intel candidates
for Test Author. Default invoke is intel only — it does not run the
suite.

## Agents

| Agent | Role |
|-------|------|
| Network Compliance | Reads the catalog from GitHub. Writes coverage and intel. Invokes Test Author / Test only when the operator asked for checks, not on an intel-only scan. |

## What it writes

- `compliance/coverage.json` — rows and counts from the job catalog
  plus NIST titles. Not a workspace copy of git.
- `compliance/intel.json` — candidates with `status: proposed`.
  Approval is a later act.

`state/compliance.json` is owned by [Test](change-and-test-agents.md)
for a compliance-suite run. That is a different file and a different
job.

Candidates are findings, not a plan. Accepted work becomes a decision
in the Sec lane when that ledger exists.
