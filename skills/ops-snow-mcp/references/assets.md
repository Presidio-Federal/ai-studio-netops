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

23 stockrooms exist. Discover them with `snow_find_stockrooms` —
do not hardcode instance names or street addresses in this skill.

Example shape (fictional):

| Stockroom | Location |
|-----------|----------|
| Example West Warehouse | Example City, CA |
| Example East Staging | Example Hub - East |

Spare-pool and pickup rooms are last-mile, not source warehouses.

### Example network gear

A demo warehouse might hold `in_stock` routers and switches. **Prefer
what `snow_find_assets` returns** over memorizing tags.

**Routers** — Catalyst 8000 family. Do not stock EoS ISR 4000 / ASR 1000
as new spares.

| Asset tag | Model | Serial | Fits |
|-----------|-------|--------|------|
| `EX-RTR-8200-A` | Cisco C8200-1N-4T | `SNEXAMPLE04` | small branch |
| `EX-RTR-8200-B` | Cisco C8200-1N-4T | `SNEXAMPLE05` | small branch |
| `EX-RTR-8300-A` | Cisco C8300-1N1S-4T2X | `SNEXAMPLE07` | medium branch |
| `EX-RTR-8300-B` | Cisco C8300-1N1S-4T2X | `SNEXAMPLE08` | medium branch |
| `EX-RTR-8300-2N-A` | Cisco C8300-2N2S-6T | `SNEXAMPLE06` | large branch |
| `EX-RTR-8500-A` | Cisco C8500-12X | `SNEXAMPLE09` | WAN hub / aggregation |

**Switches**

| Asset tag | Model | Serial | Fits |
|-----------|-------|--------|------|
| `EX-SW-9200-24P-A` | Cisco C9200L-24P-4X-E | `SNEXAMPLE10` | small branch access |
| `EX-SW-9200-24P-B` | Cisco C9200L-24P-4X-E | `SNEXAMPLE11` | small branch access |
| `EX-SW-9200-48P-A` | Cisco C9200L-48P-4X-E | `SNEXAMPLE12` | medium branch access |
| `EX-SW-9200-48P-B` | Cisco C9200L-48P-4X-E | `SNEXAMPLE13` | medium branch access |
| `EX-SW-9300-24P-B` | Cisco C9300-24P-E | `SNEXAMPLE02` | branch access, stackable |
| `EX-SW-9300-48P-A` | Cisco C9300-48P-A | `SNEXAMPLE01` | large branch access |
| `EX-SW-9500-A` | Cisco C9500-24Y4C-A | `SNEXAMPLE03` | core / distribution |

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
query that is not filtered to network gear will look wrong. To add more,
create `alm_hardware` with `install_status=6`, `substatus=available`,
and the stockroom / location **returned by find** — never a sys_id from
this skill.

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
