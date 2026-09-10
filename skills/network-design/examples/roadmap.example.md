# Network design roadmap (shape only)

Never copy these names, serials, or dates into a live run.

## Verdict

Replace the EoS group, patch PSIRT software, fix the degraded
path, and close the ranked compliance gap.

## Horizon

2026-09-10 → 2027-01-31 — path is degraded now; software
support on the estate row ends 2027-01-31.

## Environment

Prod and Dev inventories both present. No drift in this shape.

## Hardware

- **device-a** — Order C8200-1N-4T because hardware support
  ends 2027-01-31. Stock: in_stock (NETOPS-RTR-8200-A /
  Cisco C8200-1N-4T / FOC2731NETOPS4).
  1. Reserve the unit (coordinate ask).
  2. Stage on Dev, Test, cut over before that date.

## Software

- **device-a** — Update to 17.12.x because a PSIRT is on the
  product group. Qualify on Dev, then prod.

## Configuration

- **device-a** — Change WAN path / QoS to clear the degraded
  ThousandEyes test. Prove on Dev 2026-09-10, then prod.

## Compliance

- **estate** — Ranked missing control; devices are out of
  compliance until the suite passes. Author, then
  `suites=compliance` on Dev.

## Timeline

| Date | Layer | Action |
|------|-------|--------|
| 2026-09-10 | configuration | Dev path/QoS change |
| (unknown) | compliance | Author + compliance suite |
| (unknown) | software | Qualify recommended train on Dev |
| 2027-01-31 | hardware | Cut over replacement SKU |

## Warehouse

Southern California Warehouse checked. Found
NETOPS-RTR-8200-A / Cisco C8200-1N-4T / FOC2731NETOPS4.
Reserved: none (no coordinate ask). REQ: none.

## Gaps

- Compliance Test score missing.
- Trends stamp missing.

## Asks

- Why: the path change and the EoS cutover both touch the same hub.
  Question: what change window can the hub take?

