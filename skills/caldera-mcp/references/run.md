# Run a traffic test

Read `inventory/network.json` first. Then the Caldera lists. Then
create. One operation per confirm.

## 1. Network file

`devices[]` is who exists. `services[]` is what a traffic test may
open a connection to. `group` on a device is the Caldera group when
that host runs an agent (`branch`, `hq`, `cloud`, or whatever the
file says). Do not invent a group.

If the operator said to refresh the network, stop after
`references/workspace-contract.md` collect. Do not start Caldera in
that same turn.

## 2. Who is enrolled

`caldera_status`, then `caldera_get` agents with `include`.

An agent is eligible when `trusted` is true and `last_seen` is
within two hours. Match `host` to `devices[].name`. The operation
`group` is that device's `group`. Hosts in the file with no enrolled
agent are not a target. Report them in the reply. Do not deploy an
agent.

## 3. Which adversary

List adversaries with `include`. Read the chosen adversary, then the
abilities in its `atomic_ordering` (name, tactic, technique id,
technique name only).

Use an adversary when every ability tactic is `discovery` and the
ability names are probes that open a connection (port, HTTP, DNS).
The profile named `lab-probes` is that profile when it is on the
server: its abilities are network-service probes (`T1046`).

If the operator named a different adversary, use it only when it
passes the same tactic check. Otherwise refuse and name the profile
you would have used.

Planner: the one whose `name` is `atomic`.

## 4. Which source

List sources. Open the one you will use and keep `trait` plus
`value`.

Reuse a source when its `app.url` and `remote.host.ip` facts are the
same set as `services[]` for this run. `lab-probes` is the source to
compare first when that name exists.

When they differ, update the source only if the run line told you to
run. Body facts are `trait` and `value` from `services[]` only. Then
create the operation.

When no source matches and the run line did not name one, stop and
say which facts are missing. Do not create an operation with an
empty source.

## 5. Already running

`caldera_get` `/api/v2/operations/summary`. If an operation with this
adversary and this group is `state` `running`, do not create another.
Write the stamp from that operation and say it is already running.

## 6. Create

`caldera_write` `POST /api/v2/operations` with the body in
`tools.md`. `name` is `<group>-traffic-<YYYYMMDDTHHMMZ>`.

Read links once, `/api/v2/operations/{id}/links`. Keep `id`, `status`,
`paw`, `host`, `decide`, `finish`, and ability `name`, `tactic`,
`technique_id`. Drop every command field. Status `0` is complete.
Any other number is not complete. Do not poll in a loop. One read
after create is the record. The operation may still be `running`.

## 7. Write

Rewrite `security/metadata.json`. Write `security/<stamp>.json` once.
Stamp `YYYY-MM-DDTHH-MM-SSZ`. At most 10 files under `security/`;
delete older after the write. Do not delete `security/metadata.json`.

## Reply

```text
Operation: <name>
Group: <group>
Adversary: <name>
State: <running|finished|paused>
Agents: <n eligible>, <hosts skipped>
Links: <n complete> / <n read>
Wrote: security/<stamp>.json
Stimulus: <start> -> <now>
Next: none
```

`Stimulus` is the window a NetFlow or Splunk visit can correlate.
This skill does not query those systems.

Pause or finish only when the operator says pause or finish, and
names the operation. `PATCH` `state` only.
