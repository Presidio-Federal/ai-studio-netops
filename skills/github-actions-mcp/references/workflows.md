# Workflows, refs, and environments

Git refs select repository content. Workflow inputs select the environment
when the workflow supports that choice. CML labs are environments.

| Git ref | Means | `apply.yml` |
|---------|-------|-------------|
| `dev` | Proposed configs | CI — apply this commit to the Dev lab, live tests, restore the lab from `origin/main`. Does not rewrite git `dev`. |
| `main` | Prod SoT | CD — apply to Prod lab, then Dev lab (no restore), then git `dev` catches up. |

Git `compliance` holds candidate tests. Automation validates pushes there and
auto-merges successful tests to `main`. That validation is owned by the
automation repository; do not invent or manually dispatch its workflow name.

Do not pass a target / environment / lab input to `apply.yml`.
Pipeline Monitor watches the named ref and exact commit SHA. No matching
run after three list calls is `unknown`; it does not dispatch a replacement.

| Workflow | Who names it | Marker |
|----------|---------------|--------|
| `apply.yml` | Pipeline Monitor (GitOps) | `# Network test report` |
| `test.yml` | Compliance Test (ad-hoc suite) | `# Network test report` |

For `test.yml`, the requested and authorized workflow inputs choose Dev or
Production. The git ref does not identify the target environment.

Do not name `sync-dev.yml`, `reconcile-dev.yml`, `gitops-dev.yml`,
or `apply-branch-to-dev.yml`. Those are retired.

Static tests often fail while the job stays green. The marker is
the evidence. Live lines in the report gate a merge. Static fail
alone is not `fail` for GitOps merge.

## Result words (this skill)

| Word | Means |
|------|-------|
| `pass` | Live (or asked mode) in the marker passed |
| `fail` | Live (or asked mode) failed in the marker |
| `unknown` | No marker, or could not match the commit |
| `running` | Run not completed yet |

A green check is not `pass`.
