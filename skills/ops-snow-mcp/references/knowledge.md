# Knowledge draft

Operator writes Knowledge. Trends only recommends.

Authorized this turn only: they asked to draft / create / update
a KB. No recognized policy drafts a KB. Missing ask:
`status=needs_approval`, `action=noop`, no write.

Never `snow_create_knowledge` / `snow_update_knowledge` on a
board or recommend invoke. Never publish. Never invent a KB
number.

## Order

1. Read `servicenow/metadata-trends.json`. If `last_visit_id`
   is set, open that stamp. Use a cluster with `recommend` `kb`
   they named (theme / example numbers). No stamp: use the INC
   numbers they named this turn.
2. `snow_get_incident` for cited numbers — resolution from
   `close_notes` / work notes only.
3. `snow_find_knowledge` on the theme. One matching draft →
   `snow_update_knowledge`. None → `snow_create_knowledge`.
   Several published matches → recommend reuse, do not create
   a second article unless they still asked for a new draft.
4. Body is steps from those notes. Title is end-user language.
   Stay **draft**.
5. Read back `snow_get_knowledge`. Success needs number +
   sys_id + draft state.
6. Do not write `servicenow/trends/`. Next Trends scan will
   see the article.

Tools: `snow_find_knowledge`, `snow_get_knowledge`,
`snow_create_knowledge`, `snow_update_knowledge`.
