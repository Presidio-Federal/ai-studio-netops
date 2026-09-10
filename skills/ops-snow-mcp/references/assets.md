# Hardware assets (`alm_hardware`)

Used here for warehouse stock and for tracking gear on its way to a site.

## Always key on serial number

```text
snow_find_assets(serial_number=...)     # optional peek
snow_upsert_asset(serial_number=..., ...)   # create or update
```

`snow_upsert_asset` is preferred over create — it avoids the duplicate asset that
appears when a serial is received twice.

## install_status

| Status | Means | User field |
|--------|-------|------------|
| `on_order` | PO placed, not received | `owned_by` |
| `in_transit` | shipped, in the network | `owned_by` |
| `in_stock` | sitting in a stockroom, **available** | `owned_by` |
| `in_use` | installed and live | `assigned_to` |
| `retired` | end of life | clear assignment |

Only `in_stock` is shippable. An asset can appear in a stockroom while being
`in_transit` or `in_use` — filter, or you will promise gear that is already spoken
for.

ServiceNow tends to clear `assigned_to` while an asset is still in stock, so set
`owned_by` explicitly until the unit is `in_use`.

## Using the asset as a shipment record

There is no transfer-order tool, so state changes plus comments carry the
shipment:

```text
in_stock   → comments: "Reserved for CHG<n>, <site>"
in_transit → comments: "Shipping <from stockroom> -> <site>. ETA <date>."
in_use     → assigned_to set, comments: "Installed at <site> under CHG<n>"
```

Put the CHG number in the comment every time. It is the only link between the
physical unit and the change once the conversation is over.

## Stockrooms

```text
snow_find_stockrooms(search="warehouse")
snow_find_assets(stockroom=<name or sys_id>)
snow_find_locations(search=...)      # cmn_location, for the destination site
```

23 stockrooms exist. The ones holding real stock:

| Stockroom | Location |
|-----------|----------|
| Southern California Warehouse | 615 North Bush Street, Santa Ana, CA |
| San Diego South Warehouse | 815 E Street, San Diego, CA |
| Orlando FL — Staging | Presidio Hub - Orlando FL |
| Fulton MD — Staging | Presidio Hub - Fulton MD |

There are also `AE Spare Pool` and `Pickup/Dropoff` rooms, which model last-mile
handoff and make a shipment story more believable than warehouse-to-site.

### Seeded network gear

Southern California Warehouse holds thirteen `NETOPS_DEMO` units, all `in_stock`
and shippable.

**Routers** — Catalyst 8000 family only. No ISR 4000 or ASR 1000: both are
end-of-sale and stocking them as new spares does not survive scrutiny on camera.

| Asset tag | Model | Serial | Fits |
|-----------|-------|--------|------|
| `NETOPS-RTR-8200-A` | Cisco C8200-1N-4T | `FOC2731NETOPS4` | small branch |
| `NETOPS-RTR-8200-B` | Cisco C8200-1N-4T | `FOC2731NETOPS5` | small branch |
| `NETOPS-RTR-8300-A` | Cisco C8300-1N1S-4T2X | `FOC2731NETOPS7` | medium branch |
| `NETOPS-RTR-8300-B` | Cisco C8300-1N1S-4T2X | `FOC2731NETOPS8` | medium branch |
| `NETOPS-RTR-8300-2N-A` | Cisco C8300-2N2S-6T | `FOC2731NETOPS6` | large branch |
| `NETOPS-RTR-8500-A` | Cisco C8500-12X | `FOC2731NETOPS9` | WAN hub / aggregation |

**Switches**

| Asset tag | Model | Serial | Fits |
|-----------|-------|--------|------|
| `NETOPS-SW-9200-24P-A` | Cisco C9200L-24P-4X-E | `FOC2731NETOPS10` | small branch access |
| `NETOPS-SW-9200-24P-B` | Cisco C9200L-24P-4X-E | `FOC2731NETOPS11` | small branch access |
| `NETOPS-SW-9200-48P-A` | Cisco C9200L-48P-4X-E | `FOC2731NETOPS12` | medium branch access |
| `NETOPS-SW-9200-48P-B` | Cisco C9200L-48P-4X-E | `FOC2731NETOPS13` | medium branch access |
| `NETOPS-SW-9300-24P-B` | Cisco C9300-24P-E | `FOC2731NETOPS2` | branch access, stackable |
| `NETOPS-SW-9300-48P-A` | Cisco C9300-48P-A | `FOC2731NETOPS1` | large branch access |
| `NETOPS-RTR-9500-A` | Cisco C9500-24Y4C-A | `FOC2731NETOPS3` | core / distribution |

**Match gear to the site, not to the CML image name.** Lab definitions like
`cat8000v` / `iosvl2` are how the twin was built — they are not warehouse models.
List what is `in_stock`, read how big the site is from the summary, and pick a
sensible router + switch. Starting point if you need one:

| Site size | Typical router | Typical switch |
|-----------|----------------|----------------|
| Small branch | C8200-class | C9200L 24-port |
| Medium branch | C8300 1RU-class | C9200L 48-port or C9300 24-port |
| Large branch | C8300 2RU-class | C9300 48-port |

Leave aggregation (C8500) and core (C9500) in the warehouse unless the summary is
clearly a hub job. Prefer what the find-assets tool returns over memorizing SKUs.

Everything else in stock instance-wide is laptops and printers, so a warehouse
query that is not filtered to `NETOPS` will look wrong on camera. To add more,
create `alm_hardware` with `install_status=6`, `substatus=available`, stockroom
`a2aa2b3f3763100044e0bfc8bcbe5de2` and location
`f90735e70a0a0b9100de208fbc63907d`.

## Model resolution

```text
snow_find_models(search="Catalyst 9300")
```

Pass the model **sys_id** as `model=` on create or upsert. If nothing matches, ask
rather than inventing a sys_id or substituting a different model — the model is
what the field tech will look for on the box.

## Reporting

Give the asset tag, model and serial together. The model alone does not identify a
physical unit, and a field tech cannot act on it.
