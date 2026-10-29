# Layout catalog

An attached pptx is not one of the layouts below. It is `mirror`. The builder decompiles every shape (position, text, geometry) into `<customer>/deck.json` and draws those shapes on the Presidio canvas. The logo and footer stay. Colors snap to navy, orange, ink, card, and tint. Type is Arial. Do not map that deck onto `cover`, `two-column`, or `title-content`.

These are the Presidio layouts on the template's first master.
Arial and the point sizes live on the layout. Do not set a font,
a size, or a color. Do not use the second master's generic
"Title, Content" layouts. They have no Presidio sizes.

The file is the Disney–Presidio template. `cover` is Title Slide
2 Blue, the intro. It is legal on slide 1 only. The compile
refuses a second intro, and it refuses two neighboring slides
that look the same. `agenda` and `title-content` are the same
Title and Content layout, so they may not sit next to each other.

A six-slide deck looks like this:

1. `cover`
2. `agenda`
3. `section`
4. `two-column`
5. `table` or `chapter`
6. `quote`

| id | Disney layout | Use for | Slots |
|----|-----------------|---------|-------|
| `cover` | Title Slide 2 Blue | Slide 1 only. The intro. 60pt title, 24pt subtitle | `title` `subtitle` |
| `agenda` | Title and Content | The agenda. 36pt title, 28pt bullets, footer and logo | `title` `body` |
| `title-content` | Title and Content | One topic, one list. Same chrome as agenda, so not beside it | `title` `body` |
| `two-column` | 1_Two Content | A comparison or two lists. 36pt title, two 28pt columns | `title` `body` (2) |
| `section` | Section Slide | A break. 48pt white title on the blue band | `title` |
| `chapter` | Chapter Slide | A major section. 60pt title, one short line | `title` `body` |
| `quote` | Large Quote w-Subtext | A close or a statement. 54pt | `title` `subtitle` |
| `title-only` | Title Only | A stat or card row under a 36pt title | `title`, optional `blocks` |
| `table` | 1_Title and Table | A small table. 36pt title | `title` `body` `table` |

`body` is a string or a list of bullets. `two-column` `body` has
two entries. `table` is `{ "headers": ["A"], "rows": [["1"]] }`,
at most 6 columns and 8 rows.

`blocks` only on `title-only`: `bullets`, `stats` (1–3), `cards`
(1–3), or `table`. The script places them in Arial. Do not send
a position or a color.
