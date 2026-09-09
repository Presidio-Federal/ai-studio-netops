# Compliance Agents

Coverage of the job catalog against NIST titles, plus intel candidates
for Compliance Author. Default invoke is intel only — it does not run the
suite.

## Agents

| Agent | Role |
|-------|------|
| Compliance | Reads the catalog from GitHub. Writes coverage and intel. Invokes Compliance Author / Compliance Test only when the operator asked for checks, not on an intel-only scan. |
| Compliance Author | Turns an intel candidate into a check in git. Does not run the suite. |
| Compliance Test | Triggers `test.yml`, reads the job-log marker, writes the run files and risk. |

## What it writes

- `compliance/coverage.json` — rows and counts from the job catalog
  plus NIST titles. Not a workspace copy of git.
- `compliance/intel.json` — candidates with `status: proposed`.
  Approval is a later act.

`state/compliance.json` is owned by Compliance Test
for a compliance-suite run. That is a different file and a different
job.

Candidates are findings, not a plan. Accepted work becomes a decision
in the Sec lane when that ledger exists.
