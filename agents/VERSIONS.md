# Prompt versions

Deployed model is **MiniMax** unless noted.

| Agent | Version | Model |
|-------|---------|-------|
| Network Ops | 3.2.0 | Frontier (operator-selected; GitOps orchestration risk) |
| GitHub GitOps Change | 1.3.1 | MiniMax |
| Pipeline Monitor | 1.2.1 | MiniMax |
| Network Design | 3.2.2 | MiniMax |
| Ops Network Sync | 2.5.4 | MiniMax |
| Ops NetBox SoT | 1.5.2 | MiniMax |
| Ops ServiceNow | 1.5.1 | MiniMax |
| Ops ServiceNow Trends | 1.2.2 | MiniMax |
| Modernization Analysis | 2.0.1 | MiniMax |
| Modernization Lifecycle | 1.4.1 | MiniMax |
| Compliance | 1.1.0 | MiniMax |
| Compliance Intelligence | 2.0.4 | MiniMax |
| Compliance Author | 1.3.1 | MiniMax |
| Compliance Test | 1.5.0 | MiniMax |
| Health Monitor | 2.2.0 | MiniMax |
| Health Application | 1.0.1 | MiniMax |
| Health Device | 1.12.3 | MiniMax |
| Health ServiceNow | 1.8.1 | MiniMax |
| Health Analyzer | 5.0.0 | MiniMax |
| Relationship agent | 1.2.0 | MiniMax |
| Network Map | 1.0.1 | MiniMax |
| Application Map | 1.0.0 | MiniMax |

Health Device 1.12.3 (skill 1.12.6): each `execute_command` is a new container. `--workspace` is the `file_explorer` directory beside `skills` on the path Studio shows for the script. Notes separate on `=`. Boot times that are the same instant are not a reboot. Only `platform` `iosxe` is collected. Topology map is unchanged.
