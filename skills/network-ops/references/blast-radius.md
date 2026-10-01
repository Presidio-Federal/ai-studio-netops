# Blast radius and the change annotation

Before any prescription is sent — and in `recommend` and `review`
too — say what the change can reach. The answer is copied from
`state/relationships.json`, never reasoned from device names or
roles. No file, or no edge touches the targets → empty arrays and
`basis` `none`; that is a complete answer, not a gap.

## The walk (one `read_file`, mechanical)

Use only `edges[]` rows with `status` `current`. Start set **T** =
`device:<d>` for every `change.devices` item and
`interface:<d>/<i>` for every `change.interfaces` item. An
`interface:<d>/<i>` in T also puts `device:<d>` in T.

1. **Hosts.** Add to `hosts` every device the targets touch:
   - `connected_to` (symmetric): the other end of any row whose
     one end is in T. An `interface:` end counts as its device.
   - `traverses`: `from` of every row whose `to` is in T (the
     clients whose flows the target exporter saw).
   - `flows_to`: the other end of every row whose one end is in T.
   Drop the targets themselves from `hosts`. Strip the `device:`
   prefix.
2. **Applications.** `from` of every `depends_on` row whose `to`
   is `device:<h>` for h in T ∪ hosts; then, repeating until nothing
   is added, `from` of every `depends_on` row whose `to` is
   `application:<a>` already collected. Strip the prefix.
3. **Services.** `from` of every `depends_on` row whose `from` is
   `service:` and whose `to` is a collected `application:`. Strip
   the prefix.
4. **basis.** `intended` when every edge used has `basis`
   `intended`; `observed` when every edge used is `observed`
   (`asserted` counts as observed here); `both` when mixed; `none`
   when no edge was used.

Write the result to `change.blast_radius` (`hosts[]`,
`applications[]`, `services[]`, `basis`, `source_ref`
`state/relationships.json` or null when the file was absent).
Arrays are deduplicated and sorted. Nothing from `prod.json`
`role`, from `hostname` conventions, or from the problem's
`hypothesis` goes in; the compiler's edges are the only source.

Blast radius names are **not** keys. `keys` stays the union of
`change.devices`, `change.interfaces`, and relation ends.

## What it changes

- Reply: one `Blast radius:` line — `hosts <n> (<names>);
  applications <n> (<names>); services <n> (<names>); basis <b>`,
  or `none` when all three are empty.
- PR body (`implement`, after Pipeline Monitor `pass`): the same
  line verbatim under a `Blast radius` heading, after the summary.
- `relations[]` on `merged`: one `impacted` row
  `change:<commit_sha>` → `application:<a>` per
  `blast_radius.applications` item, `basis` `asserted`,
  `evidence_ref` the PR `html_url`. Not in `recommend` / `review`;
  not for hosts or services. The Analyzer joins these to its own
  `change:` follow-up.
- It never changes the prescription, the ranking, or whether to
  proceed. An operator who has authorized the change has authorized
  its reach; report it, do not ask.

## The annotation (merged only)

After `github_merge_pull_request` returns merged, and only then,
call the Grafana tool once:

```text
grafana_annotations(action="create", text="<change.summary> — PR <number>", tags=["change:<commit_sha>", "device:<d1>", "device:<d2>"])
```

- `tags` is a list of exact strings: `change:<full commit_sha>`
  first, then `device:<d>` for every `change.devices` item. No
  `interface:` tags, no `application:` tags.
- Do not pass `time`, `time_end`, `timerange`, or `limit`.
- One call. One retry on a transport error (`Connection closed`),
  same arguments. A second failure → `change.annotation_ref` null
  and a `Gaps:` line `annotation: <reason>`; the merge stands.
- Record the identifier the create response returns as a string in
  `change.annotation_ref`. Grafana not attached → null and a
  `Gaps:` line `annotation: Grafana MCP not attached`.

The Health Application nurse copies annotations tagged `change:*`
onto its board; that is how the Analyzer sees your change next to
the probes. Never create an annotation in `recommend` or `review`,
on `ci_failed`, `no_change`, `blocked`, or `failed`, or a second
time for the same SHA.
