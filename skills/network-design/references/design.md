# How to design — Network Design

The chart is the **as-built**. Your job is to say how this
network **should** be designed. Spend tokens on engineering
judgment. Pasting EoX rows, intel candidates, or visit
headlines as the roadmap is a defect.

You know how this estate is actually put together: device
roles, prod vs Dev, cables and types (NetBox), what is
reachable, how the path and syslog behave, which trains and
PSIRTs are on the boxes, which controls are missing. Use
that. Then apply how a production network is supposed to
work — WAN, routing, QoS, redundancy, management plane,
software consistency, hardware fit for role, compliance
posture that matches this network.

## What good looks like

- **Hardware** — right platform for the role (edge vs hub
  vs access), not only “Cisco named a replacement.” EoS is
  a deadline. Fit, redundancy, and warehouse stock decide
  what to order. Lab `cat8000v` / `iosvl2` are not products
  you buy.
- **Software** — one sensible train per role; patch because
  PSIRT **and** because peers should not run mixed trains
  without a reason. `recommended_software` on the row is
  evidence, not the whole design.
- **Configuration** — how the network should be built and
  operated: dual-home a single-homed WAN if the topology is
  that thin; QoS / policy-map when the path shows latency or
  loss; BGP and interface hygiene from the boxes and the
  wiring. Health degraded is one input. A quiet chart with
  a fragile design is still a config recommendation. Name
  the change; do not paste a full running-config. Do not
  invent a root cause no stamp measured — you may still
  recommend a best-practice change the as-built is missing.
- **Compliance** — which missing controls actually apply to
  **this** design (WAN, mgmt plane, logging, AAA). A
  server-only NIST title is not a network update.

`why` on every item is **your** verdict: evidence + why a
competent network would do this. Not a restatement of one
field.

## Dates and SKUs (still tight)

Cisco dates, PSIRT ids, list prices, and orderable SKUs stay
on disk or in a warehouse find. Best-practice recommendations
do not get fake ETAs or invented part numbers. If the right
design is a platform class and Cisco did not name a SKU,
say the class and **ask** — do not hallucinate a PID.

## Asks

If a competent designer would not pick without them, ask.
1–5. Why first. Never a canned questionnaire. Never “should I
open the health file.”
