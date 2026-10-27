# IOS-XE ACL

The script owns the write. These are the calls it makes if
`hai_mcp` is unavailable.

Host and port from this device's `access.restconf`. Omit username
and password. List name `SCAN-ALLOW-WEB`.

Read, then patch. Checked on a branch C8000V, RESTCONF port 4403,
2026-10-27. Patch returned 204. The list then had permit tcp
`dst-eq` 80, 443, and 8080, then deny ip.

```text
iosxe_restconf_patch
  path=Cisco-IOS-XE-native:native/ip/access-list
  host=<access.restconf.host>
  port=<access.restconf.port>
  payload=<SCAN-ALLOW-WEB with those four sequences>
```

A destination other than `any` uses `dst-host` instead of `dst-any`.

Verify with `iosxe_restconf_get` on that same path. Then
`iosxe_save_config` with the same host and port.

Remove:

```text
iosxe_restconf_delete
  path=Cisco-IOS-XE-native:native/ip/access-list/Cisco-IOS-XE-acl:extended=SCAN-ALLOW-WEB
```

That delete returned 204 and left the other extended lists in place.
The list is not applied to an interface.
