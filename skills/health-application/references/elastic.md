# Application visit — tiers and their hosts

The health check runs `scripts/visit_application.py`. This file is
the manual order when stderr says `hai_mcp unavailable`.

Tool is `elasticsearch_query`. `query` starts with `FROM`.
`timerange` is `application.window` from metadata (default `1h`).
`limit` is 200. One query per call. Do not set `timeout`.

The application is the tier. `lab.service` is that name (`web`,
`api`, `database`). `lab.application` is the business name and stays
text on the row, not a `service:` key. The docker service and
application labels are the same two fields when the lab copy is
empty. A container name such as `prod-api` or `dc-api` still carries
the tier after the hyphen. A container with no tier is not a row.
Host rows are only the hosts those containers run on.
`metrics-docker.healthcheck-prod` is the metrics agent, not the tiers.

## Queries

Containers:

```text
FROM metrics-docker.container-prod
| STATS status = MAX(docker.container.status), created = MAX(docker.container.created), image = MAX(container.image.name), lab_application = MAX(lab.application), lab_service = MAX(lab.service), label_application = MAX(docker.container.labels.application), label_service = MAX(docker.container.labels.service), site = MAX(lab.site) BY container.name, host.name
```

CPU (`docker.cpu.total.pct` is a fraction; store percent):

```text
FROM metrics-docker.cpu-prod
| STATS cpu = AVG(docker.cpu.total.pct) BY container.name, host.name
```

Memory bytes:

```text
FROM metrics-docker.memory-prod
| STATS used = MAX(docker.memory.usage.total) BY container.name, host.name
```

Host uptime:

```text
FROM metrics-system.uptime-prod
| STATS uptime_ms = MAX(system.uptime.duration.ms), site = MAX(lab.site) BY host.name
```

Host memory (`used_pct` is a fraction; available percent is 100 minus that):

```text
FROM metrics-system.memory-prod
| STATS used_pct = AVG(system.memory.actual.used.pct) BY host.name
```

Root disk:

```text
FROM metrics-system.filesystem-prod
| WHERE system.filesystem.mount_point == "/"
| STATS avail = MAX(system.filesystem.available), total = MAX(system.filesystem.total) BY host.name
```

A container row is material when it appears, vanishes, leaves `Up`,
or its created time moves by more than a minute, or CPU crosses 80
percent. The row's `application` is the tier. A host row is material
when uptime shows a reboot, or available memory or root disk crosses
10 percent. Probes and scrape targets are not queried.
