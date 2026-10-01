# Delegate and ship

Network Ops reads relevant target/peer config bodies and decides the change.
GitHub GitOps Change performs full-file edits and `dev` puts. Pipeline Monitor
owns `apply.yml` polling.

## Authorization

Questions and hypotheticals produce a read-only recommendation. Do not invoke
GitOps Change or Pipeline Monitor, put files, create a PR, or merge unless the
operator explicitly commands implementation. “How would you configure” is not
authorization. Ambiguity stays read-only.

## Handoff

Read the relevant workspace state and detailed visit. When the symptom
sits on an application or a Linux host, the boards are
`health/metadata-application.json` (probe, container, host rows) and
`health/metadata-netflow.json` (exporter, conversation rows); the
network devices to open in git are the ones `state/relationships.json`
names for that host (`connected_to`, `traverses`), never a guess from
the hostname. List `inventory/configs` on `dev`, then get only the
returned paths for the target and relevant passing/canonical peer.
Verify the finding and derive exact syntax, scope, and placement.
Before the prescription, read `state/relationships.json` once and
compute `change.blast_radius` (`references/blast-radius.md`). Invoke
GitOps Change with exact targets, operation, lines, scope, placement,
and preservation constraints. Do not include a config body.

Invoke each attached agent synchronously and wait for its final response in
the same run. Do not launch background work or query task/subagent status.

## Ship

Apply Result `submitted` → invoke Pipeline Monitor once with `workflow=apply.yml`,
`ref=dev`, and the exact commit SHA. Monitor Result `pass` → create `dev` →
`main` PR whose body carries the one-line summary and the `Blast radius`
line, then merge with `merge_method=merge`. Do not delete `dev`. Any other
terminal result → no PR and no merge.

Merged → one `grafana_annotations(action="create", …)` tagged
`change:<sha>` and each `device:<d>`; record the returned identifier in
`change.annotation_ref` (`references/blast-radius.md`). Then add the
`resolved_by` row and one `impacted` row per `blast_radius.applications`
item (`references/relations.md`).

After the terminal result, replace `state/network-ops.json` with only the
compact worker, CI, and PR evidence, `problem_ref`, `finding`,
`change.blast_radius`, `change.annotation_ref`, `relations[]`
(`references/relations.md`). Set top-level `keys` to the union of
`change.devices`, `change.interfaces`, and every relation end; never infer
from prose and never from `blast_radius`.
Allowed prefixes are
`device|interface|site|service|test|control|incident|change|application`.
Use `site:` for location and `interface:<device>/<interface>` when the device
is known; preserve nested keys. Preserve the
GitOps record in `change.operational_ref` and the Pipeline Monitor record in
`change.monitoring_ref`.

Tell GitOps Change the interface scope as `interface <name>` on a named
device; it records `interfaces[]` on its run so the change → interface edge
is a column on the run record, not a sentence.
