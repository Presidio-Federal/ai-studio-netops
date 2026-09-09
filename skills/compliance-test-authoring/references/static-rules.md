# Static rule format

Static rules run against **committed config text** in `inventory/configs/`. No
device, no lab, no credentials. They are cheap, so prefer static whenever the
question can be answered from the config.

Rules are entries in the `rules:` list of
`tests/static/schemas/<group>/rules.yml`. Unlike live checks there is no one-file-
per-rule convention — you append to the group's file.

Groups are device roles: `common`, `edge`, `wan`, `gateway`, `firewall`. **The
folder is the selector** — a rule in `wan/rules.yml` runs only on WAN devices. Put
it in `common/` only if it should apply to everything.

## Shape

```yaml
rules:
  - id: wan-bgp-asn
    category: routing
    description: "WAN router BGP ASN is 65000 (CM-6)"
    type: must_contain
    pattern: "^router bgp 65000"
    platforms: [iosxe, cat9kv]
    nist: [CM-6]
    stig: [CISC-RT-000050]
```

## Fields

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | unique across **all** groups, not just this file |
| `category` | yes | `routing`, `interfaces`, `security`, `platform` |
| `description` | yes | what is proven, with the control in parentheses |
| `type` | yes | from `rule_types` — anything else is skipped |
| `pattern` | yes | Python regex, matched multiline |
| `platforms` | yes | rule is skipped on other platforms |
| `nist` / `stig` | optional | control ids |

## Rule types

| `type` | Passes when |
|--------|-------------|
| `must_contain` | the pattern matches somewhere |
| `must_not_contain` | the pattern matches nowhere |
| `must_contain_when` | conditional — only enforced if a trigger pattern is present |
| `section_required` | a config section exists and is non-empty |
| `section_present` | a config section exists |
| `section_forbidden` | a config section does not exist |

`must_not_contain` is how you prove something stays off. "Telnet is disabled" is
not proven by the absence of a rule — it is proven by a rule that fails if anyone
adds `transport input telnet`.

## Patterns

Matched with `re.MULTILINE`, so `^` and `$` anchor to config lines. That makes
`^router bgp` reliable and avoids matching the same text inside a description or
banner.

Anchor anything that could appear as a substring elsewhere. `interface Loopback0`
matches a description mentioning it; `^interface Loopback0\b` does not.

Escape backslashes for YAML: write `"neighbor [0-9.]+ remote-as 65000"` and
`"^interface Loopback0\\b"`.

## Ids are globally unique

The engine deduplicates by id across every group a device resolves to. A device
that is both `common` and `wan` evaluates a duplicated id only once, from
whichever group resolves first — so a colliding id silently shadows another rule.
Validation catches duplicates; do not rely on it.

## Smoke it alone

The gate sets `RULE_IDS` so only your rule evaluates. Locally:

```bash
RULE_IDS=my-new-rule SCAN_DIR=inventory/configs \
  python3 -m pytest tests/static -m production -q
```

Collecting zero cases means the rule matched no device — the static equivalent of
`NOT SELECTED`. Check the group folder and the `platforms` list.

## Failing is not always wrong

A new rule that fails across every device usually means one of two things: the
pattern is wrong, or the network genuinely does not comply. Read the config before
assuming the first. If it is the second, that is a finding — report it rather than
weakening the pattern until it passes.
