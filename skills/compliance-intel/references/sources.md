# Structured compliance sources

Do not scrape HTML. Do not clone `usnistgov/OSCAL` (schemas only).

| Source | What we use | Auth |
|--------|-------------|------|
| [STIG Viewer Controls API](https://docs.stigviewer.com/controls) | 800-53 and 800-171 titles, family, identifier | None |
| [STIG Viewer Crosswalk](https://docs.stigviewer.com/crosswalk-resolve) | Optional 800-171 → 800-53 paths | SAMS token if the public call returns 401 |
| [oscal-content v1.5.0](https://github.com/usnistgov/oscal-content/releases/tag/v1.5.0) | Pinned 800-53 Rev 5.2.0 titles and related ids | None (local index) |
| NIST SP 800-171 Rev 2 Table D-1 | Fallback 800-171 → 800-53 when crosswalk is locked | None (local map) |
| Local catalog `nist:` tags | Which controls we already test | Git `catalog/job-catalog.json` via `github_get_file` |

STIG Viewer 800-171 is **Rev 2** (`3.1.7`). NIST OSCAL 800-171 is **Rev 3** (`03.01.07`). Do not mix versions silently.

DISA STIG *benchmark* downloads need a SAMS token. Do not fetch STIG maps
into the workspace. Footnotes stay titles/ids only.

Browser tools may open a STIG Viewer page to confirm the title. They are not the parser.
