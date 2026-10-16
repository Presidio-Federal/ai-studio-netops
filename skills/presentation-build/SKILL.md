---
name: presentation-build
version: "1.2.1"
description: "v1.2.1 — Use when the task says compile the deck: write <customer>/<customer>.pptx from the Disney template. Cover is slide 1 only."
---

# Presentation build

You compile one deck. The parent already wrote
`<customer>/deck.json` at the workspace root (`amtrak/deck.json`,
`acme/deck.json`). You do not change it, you do not ask the
operator anything, and you do not pick layouts.

`python-pptx` is already in the sandbox. Do not `pip install`.
There is no network. One `execute_command`, `execution_type`
`standard`.

Copy the path Studio shows for `scripts/deck.py`. It contains
`/skills/user/presentation-build/scripts/deck.py`. The words
`Internal directory` are not a path. Never pass them to `python3`.

Each run is a new container. The workspace is the `file_explorer`
folder beside `skills` on that same path. Copy that directory and
pass it as `--workspace`. Do not `cd`. `--slug` is the customer
folder in the task line (`amtrak`), not a path. Do not list the
workspace to find it. Do not write under `reports/`.

```text
python3 <copied deck.py> compile --workspace <copied file_explorer directory> --slug <customer>
```

The script copies the bundled template, drops the two sample
slides, and writes `<customer>/<customer>.pptx` next to `deck.json`.
Stdout is one JSON line: `path`, `bytes`, `slides`, `warnings`.
That line is the whole result. Do not read the pptx. Do not run
the command twice.

`ok` false: reply with that `error` and stop. The parent fixes
the JSON.

## Reply

```text
Result: ok  Wrote: <customer>/<customer>.pptx (<bytes> B, <slides> slides)
Warnings: <one line, or "none">
```

## Do not

- `write_file`, `update_text_block_in_file`, or edit `deck.json`.
- Call MCP. Do not install a package.
- Invent a customer folder. The task line has the path.
