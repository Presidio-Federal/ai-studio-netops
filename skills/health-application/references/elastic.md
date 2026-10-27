# Application visit — containers and hosts

The health check runs `scripts/visit_application.py`. This file is
the manual order when stderr says `hai_mcp unavailable`.

Tool is `elasticsearch_query`. `query` starts with `FROM`.
`timerange` is `application.window` from metadata (default `1h`).
`limit` is 200. One query per call. Do not set `timeout`.

## Queries

Containers:

```text
FROM metrics-docker.container-prod
| STATS status = MAX(docker.container.status), created = MAX(docker.container.created), image = MAX(container.image.name), application = MAX(docker.container.labels.application), service = MAX(docker.container.labels.service), site = MAX(lab.site) BY container.name, host.name
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
percent. A host row is material when uptime shows a reboot, or
available memory or root disk crosses 10 percent. Probes and scrape
targets are not queried.
