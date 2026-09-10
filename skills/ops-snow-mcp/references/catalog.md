# Catalog — ordering tickets

Ordering a catalog item is how a ticket gets opened. It creates an `sc_request`
(REQ) and one `sc_req_item` (RITM) per item, with the variables stored against the
RITM.

## Order

```text
snow_list_catalog_items(...)          # find it
snow_get_catalog_item(item_id=...)    # required — learn the variables
snow_order_catalog_item(item_id=..., variables={...})
snow_get_request(...)                 # read back the REQ number
```

Cart path when ordering several things: `snow_add_to_cart` → confirm →
`snow_checkout_cart` → `snow_get_request`. Helpers: `snow_update_cart_item`,
`snow_remove_from_cart`, `snow_clear_cart`.

Confirm the item name with the user before ordering. Never guess variable names —
read them from `snow_get_catalog_item`.

## Items used by this demo

| Item | sys_id | Variables |
|------|--------|-----------|
| Network Port Provisioning | `1dee557a2f3b729482ae474fafa4e380` | device_name, interface_name, vlan_id, ip_address, port_description, business_justification |
| Add network switch to datacenter cabinet | `508e02ec47410200e90d87e8dee49058` | none |
| Change VLAN on a Cisco switchport | `b1c8d15147810200e90d87e8dee490f7` | none |
| Clear BGP sessions on a Cisco router | `d6c2273c47010200e90d87e8dee49004` | none |

Prefer resolving by name; sys_ids differ per instance.

### Gotchas, both found by testing

**`ip_address` rejects CIDR.** The label says "IP Address (with prefix)" but the
validator wants a bare address. `100.64.7.1/30` fails the whole order with "Not a
valid IP address". Send `100.64.7.1` and put the mask in `port_description`.

**Ordering does not create a change request.** The last three items above are
classed "Standard Change Template" and look like they should produce a CHG. They
do not — ordering them yields a REQ and RITM like any other item. Verified with
REQ0010101 and REQ0010102. Report the REQ; do not call it a change.

All variables on Network Port Provisioning are non-mandatory, so nothing stops a
useless ticket being submitted. Fill all of them.

## Demo records

Everything created while validating this skill is marked `NETOPS_DEMO` and can be
removed with one query per table:

| Table | Query | Records |
|-------|-------|---------|
| `change_request` | `short_descriptionLIKENETOPS_DEMO` | CHG0031457 |
| `sc_request` | `short_descriptionLIKENETOPS_DEMO` | REQ0010101, REQ0010102 |
| `sc_req_item` | `short_descriptionLIKENETOPS_DEMO` | RITM0010097, RITM0010098 |
| `alm_hardware` | `commentsLIKENETOPS_DEMO` | FOC2731NETOPS1/2/3 |

`CHG0031457` is a hand-built reference change with implementation, backout and
test plans populated — worth keeping as an example of the target shape, since
almost every real change on this instance leaves those fields empty.
