# Change from SoT

Git branches are config data. CML labs are topologies. You edit
files in git. Apply is GitOps on the git ref.

## Config path

`inventory/configs/<hostname>` — hostname copied from inventory
(`AI-CLOUD-EDGE`, `WAN-01`). 404 on `ref=dev` → same path
`ref=main`. Still 404 → `<hostname>.cfg` on `dev` then `main`.
That is the whole search.

`github_get_file` returns `content` and `sha`. You need both for
`github_put_file`.

## Peer template

A failed check on one role and a pass on another is a config
gap, not a mystery.

1. List failing hostnames from `state/testing.json` /
   `state/compliance.json` `gaps` (or the latest stamp those
   files name).
2. Find a peer that passed the same check, or a same-role
   neighbor that has the feature in git (WAN has NTP; edge does
   not).
3. `github_get_file` both devices.
4. Copy **only the missing stanza** from the working peer into
   the failing file. Keep the rest of the failing file. Do not
   replace the whole running-config with the peer’s file.
5. Do not invent addresses, keys, or servers. If the peer has
   no usable stanza, `blocked` — say what is missing.

A checker traceback or `dict` has no attribute is `test_bug` —
Compliance Author.

## NTP (estate example)

Compliance: edges fail `ntp-synchronized` / `ntp-associations-iosxe`.
WAN does not. `AI-CLOUD-EDGE` in git has no `ntp` stanza. `WAN-01`
does. Add the WAN NTP servers/peers to each failing edge file the
same way WAN declares them (`ntp server` / `ntp peer` as written
on WAN). Then `github_put_file` each changed file `ref=dev`.

One commit message covering the set is fine if you put files in
sequence; each `github_put_file` is one commit on `dev`. Prefer
one file per call. Monitor the **last** `commit_sha`.

## After the commit

Pipeline Monitor watches `apply.yml` on `ref=dev` for that
`commit_sha`. CI applies the commit to the Dev lab, runs tests,
restores the lab from `main`. Git `dev` keeps the commit.

Merge only when the monitor Result is `pass` for **live**. Static
noise is not a block. Then PR `dev` → `main` (merge commit). CD on
`main` applies Prod, then Dev. You do not restore git `dev`.
