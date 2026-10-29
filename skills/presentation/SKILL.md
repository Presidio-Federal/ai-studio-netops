---
name: presentation
version: "1.3.0"
description: "v1.3.0 — Use when drafting a Presidio deck, or when an attached pptx should be decompiled and rebuilt on the Disney template."
---

# Presentation skill

Each customer is one folder at the workspace root. Nothing goes
under `reports/` or a second presentations tree.

The folder is every word they said, lowercased, spaces as
hyphens. Do not drop a word and do not add one. "Acme" is
`acme`. "Acme Corp" is `acme-corp`.

`read_file`, `write_file`, and `update_text_block_in_file` take
`<customer>/deck.json`. "Acme Corp" is filePath
`acme-corp/deck.json`.

Do not put `file_explorer/` on a filePath. That string is
resolved as `/app/file_explorer/...` and Access denied. File
not found on `acme-corp/deck.json` means there is no deck yet.
An attached pptx is the Restyle section. Otherwise write it at
that same path. Do not retry with a `file_explorer/` prefix.

| Tool | Argument |
|------|----------|
| `get_folder_structure` | `file_explorer` |
| `read_file` `write_file` `update_text_block_in_file` | `<customer>/deck.json` |

`write_file` creates `<customer>/`. Do not `mkdir`. Do not
`execute_command` to make a folder or to edit JSON.

## Restyle an attached pptx

An attached pptx is already a deck. They asked to add it or rebuild it on the Disney template. Do not read it and propose an outline. Do not ask New or Existing. Do not pick `cover`, `two-column`, or `title-content`. Follow `references/layouts.md` for what `mirror` means.

The folder is the customer they named. "the disney workspace" is `disney`. A word that only names the workspace or the template is not part of the folder. If they did not name a customer, ask who it is for and stop.

Do not write `deck.json` yourself. The builder decompiles the file. Invoke **Presentation Builder** and end the turn.

```text
Restyle the deck only. Slug: <customer> Source: <path Studio showed for the pptx>
```

Copy that path. Do not invent a directory. If the result says the source pptx is missing, copy the path Studio showed and invoke again. When the result arrives, quote it. A later change to one string already in the file is `update_text_block_in_file`, then the Compile task. Do not restyle again.

## Choose the deck

Call `ask_user_question` when you do not already know: New or Existing.

**New.** If they only said "new", ask who it is for and stop. Do
not invent a name. First tool is `read_file` filePath
`acme-corp/deck.json` when they said Acme Corp. Do not read
layouts first. File not found means there is no deck. If the
file is already there, say so and stop. After they confirm the
outline, `write_file` the same path.

**Existing.** Ask who it is for when they have not said. If they
named the customer, `read_file` `<customer>/deck.json` and no
other path. If they did not, one `get_folder_structure` of
`file_explorer` and no other directory. The customer folders
are the top-level names. Several matches: `ask_user_question`
with those names. File not found on `<customer>/deck.json` is
"no deck for that name". Access denied on a `file_explorer/`
filePath means you added a prefix. Drop it and use
`<customer>/deck.json`. Do not search anywhere else.

## Layouts

Follow `references/layouts.md`. The template is the Disney file.
Slide 1 is `cover` and no other slide is. Do not put `agenda`
next to `title-content`. Mix `section`, `two-column`, `chapter`,
`quote`, and `table`. Do not set a font.

## Write the deck

Layouts and slots are `references/layouts.md`. The file shape is
`examples/deck.example.json` and `schemas/deck.schema.json`.
`keys` is `[]`. `source_agent` is `presentation`. `slug` is the
folder name.

A new deck or a new slide: `write_file` replaces
`<customer>/deck.json`. A change to one bullet or one string
already in the file: `update_text_block_in_file` on that text
only. `read_file` `<customer>/deck.json` first so the old text
matches. Do not rewrite the file for a one-line edit. Do not
read the pptx.

Slides stay numbered from 1 with no gaps. Replacing slide 3 does
not touch the others. The next number appends. You do not insert
in the middle.

Every write of `deck.json`, including a one-line edit, is
followed by Presentation Builder in that same turn. Do not
wait for them to say build. Do not say the PowerPoint is
unchanged.

## Build

You do not run `deck.py`. After the write, invoke
**Presentation Builder** once, then end the turn. Do not wait,
poll, or check its status. The result comes back when you are
idle. If the error says two slides share a layout, or a slide
after slide 1 is `cover`, fix the JSON and invoke again. Do
not ask them to fix the layouts. Task line:

```text
Compile the deck only. Path: <customer>/deck.json
```

Not a generic helper. Not a self clone. If Presentation Builder is
not attached, say so and stop. When its result arrives, quote
that summary. Then you can keep editing JSON. Compile again
only when they ask.

## Do not

- Create `reports/`, `presentations/`, or any folder above the
  customer name.
- Call MCP, or `pip install`. `python-pptx` is already in the
  sandbox, and you are not the one who runs it.
- Invent a layout id, a position, a color, a footer, or a logo.
- Read another agent's files unless they point at a path. Copy
  that field into the deck. Do not collect telemetry.
