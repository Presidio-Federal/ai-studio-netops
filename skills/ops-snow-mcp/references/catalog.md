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

Resolve catalog items **by name** on this instance. sys_ids differ per
instance — do not copy ids from this skill.

| Item | Variables |
|------|-----------|
| Network Port Provisioning | device_name, interface_name, vlan_id, ip_address, port_description, business_justification |
| Add network switch to datacenter cabinet | none |
| Change VLAN on a Cisco switchport | none |
| Clear BGP sessions on a Cisco router | none |

### Gotchas, both found by testing

**`ip_address` rejects CIDR.** The label says "IP Address (with prefix)" but the
validator wants a bare address. `100.64.7.1/30` fails the whole order with "Not a
valid IP address". Send `100.64.7.1` and put the mask in `port_description`.

**Ordering does not create a change request.** The last three items above are
classed "Standard Change Template" and look like they should produce a CHG. They
do not — ordering them yields a REQ and RITM like any other item. Verified with
REQ0001001 and REQ0001002. Report the REQ; do not call it a change.

All variables on Network Port Provisioning are non-mandatory, so nothing stops a
useless ticket being submitted. Fill all of them.

## Demo records

Everything created while validating this skill is marked `NETOPS_DEMO` and can be
removed with one query per table:

| Table | Query | Records |
|-------|-------|---------|
| `change_request` | `short_descriptionLIKENETOPS_DEMO` | CHG0001001 |
| `sc_request` | `short_descriptionLIKENETOPS_DEMO` | REQ0001001, REQ0001002 |
| `sc_req_item` | `short_descriptionLIKENETOPS_DEMO` | RITM0001001, RITM0001002 |
| `alm_hardware` | `commentsLIKENETOPS_DEMO` | SNEXAMPLE01/02/03 |

`CHG0001001` is a hand-built reference change with implementation, backout and
test plans populated — worth keeping as an example of the target shape, since
almost every real change on this instance leaves those fields empty.
