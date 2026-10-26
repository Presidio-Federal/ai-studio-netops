# Campaign visit

Read the boards first. Then list Caldera. Do not read a network map
and do not call a device.

## 1. What to keep

`caldera_status`, then the lists in `tools.md`.

**Agents.** Keep a row when `trusted` is true and `last_seen` is
under two hours. `group` is the group the agent reported. `device`
is `host`. Write `campaigns/agents/enrolled.json`.

**Abilities.** Keep a row when the tactic is `discovery` and the
name contains scan, probe, sweep, or port, and a linux executor
exists. Also keep an ability id that a `lab-` adversary already
lists. Store id, name, tactic, technique id, and why it was kept.
Write `campaigns/abilities/relevant.json`. Discard every other
ability. There are thousands. Do not page them into the workspace.

**Adversaries.** Keep a row whose name starts with `lab-`, or whose
`atomic_ordering` is entirely inside the relevant ability ids.
Write `campaigns/adversaries/relevant.json`.

**Facts.** Open a source only when its name starts with `lab` or
an operation on the summary points at it. Keep a fact whose trait
is `app.url` or `remote.host.ip`. Write `campaigns/facts/lab.json`.

**Operations.** From the summary, keep a row whose name starts with
`lab-` or whose group matches an enrolled agent. A new id, or a
`state` that differs from `campaigns/metadata.json` `current_operation`,
is material: write `campaigns/operations/<stamp>.json` with link
rows (host, paw, ability name, technique id, status). Status `0`
is complete.

## 2. Learn

On `campaigns/metadata.json` set `next_test` only from this visit's
links. An ability that finished with status `0` is worth repeating.
A link that did not finish is not. `why` is one sentence. Leave
`next_test` null when nothing new was learned.

## 3. Run

Only on a run line. Read the five files. Do not collect again in
the same turn unless the operator also said to refresh.

Group is the one they named. Adversary is the one they named, else
`next_test.adversary`, else the relevant adversary whose abilities
are scans. Targets are values already in `facts/lab.json`. When
those facts do not cover the targets they named, `PUT` the source
with `trait` and `value` only, then create the operation.

Planner name `atomic`. `autonomous` 1. One read of the links after
create. Write the stamp. Set `next_test` from what you started.

## Reply

Collect:

```text
Visit: campaign
Coverage: caldera <complete|partial|unavailable>
Agents: <n> enrolled
Abilities: <n> kept
Adversaries: <n> kept
Facts: <n>
Next test: <adversary or none>
Wrote: campaigns/metadata.json
```

Run:

```text
Operation: <name>
Group: <group>
Adversary: <name>
State: <state>
Wrote: campaigns/operations/<stamp>.json
Next test: <what the following visit should repeat or drop>
```
