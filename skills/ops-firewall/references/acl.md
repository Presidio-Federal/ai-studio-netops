# IOS-XE ACL

Host and port from this device's `access.restconf`. Omit username
and password.

Read first:

```text
iosxe_restconf_get
  path=Cisco-IOS-XE-native:native/ip/access-list
  host=<access.restconf.host>
  port=<access.restconf.port>
```

Checked on a lab C8000V, 2026-10-26. The body is
`Cisco-IOS-XE-native:access-list` /
`Cisco-IOS-XE-acl:extended[]`. Each list has `name` and
`access-list-seq-rule[]`. A rule has `sequence` and `ace-rule`
(`action`, `protocol`, and the match leaves, such as `any` and
`dst-any`).

Add: `iosxe_restconf_patch` the same path. Payload is that object
with the named list and the new sequence only. Copy `ace-rule` from
a rule the GET returned, and change only the fields the operator
named.

Replace: `iosxe_restconf_put` of the GET object with those fields
changed. PUT overwrites the resource you send.

Remove: `iosxe_restconf_delete` the named list. Do not delete a list
the operator did not name.

Verify with the same GET. Then `iosxe_save_config` with the same
host and port. A write that does not verify is `failed`. Do not save
it.
