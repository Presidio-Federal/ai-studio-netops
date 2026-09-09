# Digital twin from NetBox (infrastructure only)

Use when the user wants a CML lab from **what is wired in NetBox**, not from Prod CML JSON and not from running-config.

NetBox supplies: device name, role, manufacturer, device_type, interface inventory, cables.
Git / Network Sync supplies: configs (`inventory/configs`). Twin applies them
(`sync-dev` via Sync; `deploy-twin.yml` is Twin's intent, Sync runs the YAML).
Never invent config from interface descriptions or IP addresses in NetBox.

## Read order

1. Read `state/netbox.json` if it exists. Envelope first (`status`, `headline`,
   `kind`). Use `links[]` for wiring (device + interface names). `kind: git`
   → stop (infra is not NetBox). `failed` or missing details → go to step 3.
   `ok` or `gaps` → open the details file if you need ids or types.
2. Read `inventory/infra-sot.json` if it exists and `status` is `ok` or `gaps`.
   Use `devices[].name`, `device_type`, `role`, nested `interfaces[].name`, and
   `cables[]` (`a_device` / `a_interface` / `b_device` / `b_interface`).
   Do not `netbox_find` when this file is present and not `failed`.
3. Missing snap, `status` failed, or envelope stale → `netbox_test_connection`,
   then `netbox_find(object_type="device")` for the tenant, per-device
   `netbox_find(object_type="interface", device=<name>)`, then
   `netbox_find(object_type="cable")`.

Present **links** first (who is cabled to whom). Then build CML.

## Map to CML

| NetBox / snap | CML |
|---------------|-----|
| `device.name` | node `label` |
| `manufacturer` + `device_type` | `cml_list_node_definitions` / image — **explicit map or ask**. Do not silently substitute (e.g. C9300 → cat8000v) without saying so |
| interface names | expected port names after boot; CML images often have **fewer** ports than the live box |
| cable `A device:iface` ↔ `B device:iface` | `cml_connect_nodes` after both nodes exist (UUIDs, not labels) |

Skip Loopback / Vlan / virtual cables unless the user asked. Skip cables whose far-end device is not in the device list.

If the CML image has fewer physical ports than NetBox:

- Connect the cables that fit; list the rest as gaps
- Do not invent extra CML interfaces
- Do not copy a peer device's interface block into bootstrap (existing twin rule)

## Config (separate step)

After topology exists:

- Apply configs from the **config SoT** (Network Sync / `inventory/configs` / `cml_apply_configs` with files from git)
- Do not generate a full running-config from NetBox IPs
- Bootstrap DHCP/OOBM stays a CML concern, not a NetBox field

## `inventory/infra-sot.json`

Written by populate (schema `infra-sot/v1`). Twin may rely on names and cable
ends. Ids are for populate re-runs, not for CML. No YANG, no NetBox raw
objects, no configs.
