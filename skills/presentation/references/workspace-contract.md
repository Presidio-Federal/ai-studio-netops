# Workspace contract — Presentation

This workspace is the customer's decks. It is not the network-ops
tree. Do not read `workspace-handoff` for these paths.

| Tool | Argument |
|------|----------|
| `get_folder_structure` | `file_explorer` |
| `read_file` `write_file` `update_text_block_in_file` | `<customer>/deck.json` |

"Acme Corp" is `acme-corp/deck.json`. "Amtrak" is
`amtrak/deck.json`.

`file_explorer/acme/deck.json` is `/app/file_explorer/acme/deck.json`
and Access denied. Do not send that. File not found on
`<customer>/deck.json` means the deck is not there yet.

The compile script writes `<customer>/<customer>.pptx` beside the
JSON. No agent reads the pptx. No index file. No envelope.
`keys` is `[]`.
