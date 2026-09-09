---
description: Conventions for creating skills targeting the AI Studio platform. Covers filesystem layout, path conventions, script patterns, and skill structure that work correctly in the AI Studio sandboxed runtime.
globs: "**/SKILL.md,**/skills/**/*.py,**/skills/**/*.md"
alwaysApply: false
---

# AI Studio Skill Authoring

## Platform Filesystem

AI Studio runs agents in a sandboxed container with a specific filesystem layout. All paths in skills MUST use these conventions.

### Key Directories

| Path | Purpose | Writable |
|------|---------|----------|
| `/skills/user/<skill-name>/` | User-installed skills (scripts, data, references) | No |
| `/skills/global/<skill-name>/` | Global/shared skills | No |
| `/workspace/` | User's working directory (uploaded files land here) | Yes |
| `/code_output/` | Output directory for generated files | Yes |

### Path Rules

- **Skill assets** (scripts, data files, reference CSVs): Always reference via `/skills/user/<skill-name>/...`
- **User inputs** (uploaded PDFs, CSVs, etc.): Always read from `/workspace/`
- **Generated outputs** (annotated PDFs, reports, HTML): Always write to `/workspace/` or `/code_output/`
- **Never** write to `/skills/` — it's read-only at runtime
- **Never** use relative paths for skill assets — always use absolute `/skills/user/...` paths

### Finding Skill Paths at Runtime

Because the skill may be installed as user or global, include a discovery step:

```bash
# Find where the skill is installed
SCRIPT=$(find /skills -name "my_script.py" 2>/dev/null | head -1)
```

Or check these locations in order:
1. `/skills/user/<skill-name>/scripts/` (most common)
2. `/skills/global/<skill-name>/scripts/` (if globally installed)

## Skill Structure

Every skill is a single root folder containing a `SKILL.md` and optional supporting files:

```
<skill-name>/
├── SKILL.md              # Required — main instructions with YAML frontmatter
├── references/           # Optional — detailed docs loaded on demand
│   ├── guide.md
│   └── examples.md
├── scripts/              # Optional — pre-built Python/bash scripts
│   ├── main_script.py
│   └── requirements.txt
└── data/                 # Optional — static data files (CSVs, templates)
    └── reference_data.csv
```

### SKILL.md Frontmatter (Required)

```yaml
---
name: my-skill-name          # Max 64 chars, lowercase + hyphens only
description: What this skill does and when to use it. Be specific — include trigger terms.
---
```

### Packaging

Skills are distributed as `.zip` files with **exactly one root folder**:

```
my-skill.zip
└── my-skill/
    ├── SKILL.md
    └── ...
```

**Never** include multiple root folders in a zip. **Never** include the agent prompt in the skill zip — agent prompts are configured separately.

## Writing Scripts for AI Studio

### Python Script Conventions

Scripts must work in the sandboxed AI Studio runtime:

```python
#!/usr/bin/env python3
"""Brief description of what this script does."""

import os
import sys
from pathlib import Path

# Resolve paths relative to the script, not the working directory
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"

# Read static data from the skill's data/ directory
DATA_FILE = DATA_DIR / "reference_data.csv"

# Accept input paths as arguments (files from /workspace/)
input_path = sys.argv[1]

# Write output to /workspace/ or subdirectory
output_dir = os.path.join(os.path.dirname(input_path), "output")
os.makedirs(output_dir, exist_ok=True)
```

**Key patterns:**
- Use `Path(__file__).resolve().parent` to find sibling data files — never hardcode `/skills/user/...` inside the script itself
- Accept input file paths as CLI arguments
- Print structured output (JSON) to stdout for the agent to parse
- Print errors/warnings to stderr
- Create output subdirectories with `os.makedirs(output_dir, exist_ok=True)`

### requirements.txt

Always include a `requirements.txt` in `scripts/` if the script has pip dependencies:

```
pdfplumber
pypdf
reportlab
```

The SKILL.md must include a prerequisites step:

```bash
pip install -r /skills/user/<skill-name>/scripts/requirements.txt
```

### Script Invocation in SKILL.md

Always show the full path pattern and quote file arguments:

```bash
python3 /skills/user/<skill-name>/scripts/my_script.py "/workspace/<filename>"
```

## Writing SKILL.md Content

### Workflow Steps

Structure the SKILL.md as a numbered workflow the agent follows:

1. **Prerequisites** — install dependencies if any
2. **Get input onto filesystem** — if user attached a file, save to `/workspace/`; if referencing an existing file, use that path
3. **Run the script/tool** — exact command with full paths
4. **Present results** — tell the agent how to summarize output (brief and actionable, not raw dumps)

### Referencing Skill Files

Use relative references in markdown links for progressive disclosure:

```markdown
For detailed specs, see [sizing-guide.md](references/sizing-guide.md)
```

The agent reads these files on demand — they don't all load at once.

### Output Presentation Rules

Always tell the agent:
- What to summarize vs. what to skip
- The expected output format (JSON to stdout, file to disk, etc.)
- Where the output file ends up (`/workspace/...` or `/code_output/...`)

## Agent Prompts

Agent prompts are **separate from skills** — they are configured on the agent, not bundled in the skill zip.

Keep agent prompts lean:
- Identity (who the agent is)
- Purpose (what it does)
- Success criteria (what good looks like)
- Audience (who consumes the output)

All operational logic (tool parameters, workflows, validation rules) belongs in the skill, not the agent prompt.

## Common Mistakes

- Writing outputs to `/skills/` (read-only — will fail)
- Using relative paths like `./scripts/` in SKILL.md (won't resolve in the agent runtime)
- Hardcoding `/skills/user/` inside Python scripts (use `Path(__file__)` instead)
- Including multiple root folders in the zip
- Including the agent prompt in the skill zip
- Dumping raw script output to the user instead of summarizing
- Missing `requirements.txt` when scripts have pip dependencies
- Not quoting file paths in bash commands (spaces in filenames break things)
