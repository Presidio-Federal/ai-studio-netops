# Change from SoT

Git branches are config data. CML labs are topologies. You edit
files in git. Apply is GitOps on the git ref.

## Config path

`github_list_files` `path=inventory/configs` `ref=dev`. The file
is `entries[].path` for that hostname — suffix included as listed.
Then `github_get_file` that path `ref=dev`. Keep `content` and
`sha`. Put the same path. Do not build a filename.

## Named edit

Operator names device + line (description, one stanza): list,
get the listed path, change only the named text, `github_put_file`
the full file `ref=dev` with `sha` from get. No peer.

## Peer template

A failed check on one role and a pass on another is a config
gap, not a mystery.

1. List failing hostnames from `state/testing.json` /
   `state/compliance.json` `gaps` (or the latest stamp those
   files name).
2. Find a peer that passed the same check, or a same-role
   neighbor that has the feature in git (WAN has NTP; edge does
   not).
3. List once, then `github_get_file` both listed paths.
4. Copy **only the missing stanza** from the working peer into
   the failing file. Keep the rest of the failing file. Do not
   replace the whole running-config with the peer’s file.
5. Do not invent addresses, keys, or servers. If the peer has
   no usable stanza, `blocked` — say what is missing.

A checker traceback or `dict` has no attribute is `test_bug` —
Compliance Author.

## NTP (estate example)

Compliance: edges fail `ntp-synchronized` / `ntp-associations-iosxe`.
WAN does not. List `inventory/configs`, get the listed files for
the failing edges and a WAN that has `ntp`. Add the WAN NTP servers/peers to each failing edge file the
same way WAN declares them (`ntp server` / `ntp peer` as written
on WAN). Then `github_put_file` each changed file `ref=dev`.

One commit message covering the set is fine if you put files in
sequence; each `github_put_file` is one commit on `dev`. Prefer
one file per call. Pass the **last** `commit_sha` to Pipeline
Monitor. Never omit it.

## After the commit

Pipeline Monitor watches `apply.yml` on `ref=dev` for that
`commit_sha`. CI applies the commit to the Dev lab, runs tests,
restores the lab from `main`. Git `dev` keeps the commit.

Merge only when the monitor Result is `pass` for **live**. Static
noise is not a block. Then PR `dev` → `main` (merge commit). CD on
`main` applies Prod, then Dev. You do not restore git `dev`.
