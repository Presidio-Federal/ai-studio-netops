# Change from SoT

Configs are GitHub files. List the configs directory, get the
listed path, put `ref=dev`. Do not write the Studio workspace.

## Named edit

`github_list_files` `ref=dev`. Use `entries[].path` for the
hostname in the ask. `github_get_file` that path. Change only
the named text. `github_put_file` the full file `ref=dev` with
`sha` from get.

## After the commit

Invoke Pipeline Monitor with that `commit_sha`. Do not poll
Actions yourself. Merge `dev` → `main` only if live Result is
`pass`. Static fail is not a merge block. Do not delete `dev`.
