# Problem, relations, keys

Network Ops is the one agent that reads both the chart and the
config. What it concludes from the two is worth recording as
edges — asserted, with the git path as evidence — so the Analyzer
can confirm or refute the treatment and the Relationship agent can
draw the graph. Three rows are allowed. Nothing else.

## Start from the problem list

`read_file` `state/health.json` first when it exists. Its
`problems[]` (`id`, `status`, `keys`, `symptom_refs`,
`evidence_refs`, `hypothesis`, `order`) is the chart. Match the
ask to **one** problem:

- the Analyzer's order text is `Network Ops: <hypothesis>` — the
  hypothesis string is on the problem, take its `id`;
- the operator named a key on the problem (`device:`, `test:`,
  `service:`, `incident:`) or its symptom in plain words
  (`the CLOUD-to-HQ loss`) and exactly one `active` or `watching`
  problem carries that key or test name.

Two problems fit, or none → `problem_ref` null and say so in
`Gaps:`. Never pick one to have one.

With a match: `problem_ref` = its `id`; `finding.source` =
`health:<id>`; `finding.headline` starts from `hypothesis`; read
its `symptom_refs` and `evidence_refs` (at most four files, the
newest first) **before** listing configs — they say which device,
interface, or path to open in git. A `resolved` problem is not
treated; answer that it is resolved and stop.

`state/health.json` absent, or no `problems[]` → `problem_ref`
null, `finding.source` `operator` or the record path you used.

## `finding.verified_in_git`

`true` only when you read the target body **and** a passing or
canonical peer body on `dev` and the difference named in
`finding.headline` is literally there (a missing line, a wrong
value, an ACL entry). `false` when the fix is inferred (the chart
says the segment is bad, git shows no difference; the fix is a
counter reset, a test change, a hypothesis). `kind`:
`missing_config` / `wrong_config` need `verified_in_git` true;
`test_bug` and `other` may be either.

## The three rows

All `basis` `asserted`. Both ends in `keys`. `evidence_ref` is the
git path you read (`inventory/configs/<file>` exactly as listed)
for the first two, the PR `html_url` or `change.monitoring_ref`
for the third.

| rel | from → to | write when |
|-----|-----------|------------|
| `depends_on` | `test:<id>` or `service:<name>` (from the problem's `keys`) → `device:<target>` or `interface:<device>/<interface>` (the prescription's targets and scope) | `problem_ref` set and the problem has a `test:` or `service:` key. Both modes. One row per target device or interface, not both for the same device. |
| `caused` | `device:` / `interface:` (the target) → `test:` / `service:` / `incident:` (from the problem's `keys`) | `finding.verified_in_git` true **and** `kind` is `missing_config` or `wrong_config`. Both modes. The config difference is the cause you are asserting; the Analyzer's `outcome` says whether you were right. |
| `resolved_by` | `test:` or `incident:` (from the problem's `keys`) → `change:<commit_sha>` | `status` `merged` only. One row per test/incident key on the problem. |

Not a relation: the peer you compared against (`change.peer` is
the column), a device the problem names but you did not touch,
anything the chart already says (`impacted` is the Analyzer's),
a hypothesis with `verified_in_git` false (it is `depends_on` at
most, never `caused`).

`change:<commit_sha>` is the full SHA `git.commit_sha`. It is a
key on this record only when a `resolved_by` row uses it.

## `keys`

Exactly the union of: `device:<d>` for every `change.devices`
item, `interface:<d>/<i>` for every `change.interfaces` item,
and every `relations[].from` / `.to`. Nothing from `headline`,
`summary`, `finding`, or the problem's own keys unless a relation
brought them in. `change.interfaces` lists every interface stanza
the prescription's `Scope` names — `WAN-01/GigabitEthernet4`
spelled as in the config — and is empty for a global scope.

Validate with `scripts/validate_network_ops.py`; it recomputes
the union and rejects a relation whose ends are not both in
`keys`.
