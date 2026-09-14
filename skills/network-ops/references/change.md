# Change from SoT

Git branches are config data. CML labs are topologies. You edit
files in git. Apply is GitOps on the git ref.

## Config path

`github_list_files` `path=inventory/configs` `ref=dev`. The file
is `entries[].path` for that hostname — suffix as listed. Then
`github_get_file` that path `ref=dev`. Keep `content` and `sha`.
Put the same path. Do not build a filename.

## Named edit

Operator names device + line: list, get the listed path, change
only the named text, `github_put_file` the full file `ref=dev`
with `sha` from get.

## After the commit

Pipeline Monitor watches `apply.yml` on `ref=dev` for that
`commit_sha`. CI applies the commit to the Dev lab, runs tests,
restores the lab from `main`. Git `dev` keeps the commit.

Merge only when the monitor Result is `pass` for **live**. Static
noise is not a block. Then PR `dev` → `main` (merge commit). CD on
`main` applies Prod, then Dev. You do not restore git `dev`.

Pass the **last** `commit_sha` to Pipeline Monitor. Never omit it.
