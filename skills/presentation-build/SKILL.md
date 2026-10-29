---
name: presentation-build
version: "1.3.0"
description: "v1.3.0 — Use when the task says compile or restyle: rebuild the deck on the Disney template from deck.json or a decompiled pptx."
---

# Presentation build

You compile one deck. On compile, the parent already wrote
`<customer>/deck.json` (`amtrak/deck.json`, `acme/deck.json`).
On restyle, the script decompiles the attached pptx into that
file. You do not edit it by hand, you do not ask the operator
anything, and you do not pick layouts.

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

Compile:

```text
python3 <copied deck.py> compile --workspace <copied file_explorer directory> --slug <customer>
```

Restyle, when the task line starts with `Restyle the deck only`:

```text
python3 <copied deck.py> restyle --workspace <copied file_explorer directory> --slug <customer> --source <copied pptx path>
```

`--source` is the path in the task line. Do not invent a directory. Do not read the pptx. The script decompiles every shape into `<customer>/deck.json` (`layout` `mirror`: position, text, geometry), then draws those shapes on the Presidio canvas. The logo and footer stay. Colors snap to navy, orange, ink, card, and tint. Type is Arial. You do not choose layouts.

Either command copies the bundled template, drops the sample slides, and writes `<customer>/<customer>.pptx` next to `deck.json`. Stdout is one JSON line: `path`, `bytes`, `slides`, `warnings`. That line is the whole result. Do not read the pptx. Do not run the command twice.

`ok` false: reply with that `error` and stop.

## Reply

```text
Result: ok  Wrote: <customer>/<customer>.pptx (<bytes> B, <slides> slides)
Warnings: <one line, or "none">
```

## Do not

- `write_file`, `update_text_block_in_file`, or edit `deck.json` by hand. On restyle the script writes it.
- Call MCP. Do not install a package.
- Invent a customer folder. The task line has the path.
