---
summary: Pending-work board: read-write sharing policy, staff onboarding with pre-created SSO links, optional NAS staging move, base-image digest pin, Elasticsearch.
kind: living
status: current
read-when: checking in-flight or unverified work
---

Pending work, moved out of AGENTS.md on 2026-11-11. Keep this board current instead of adding entries to AGENTS.md.


| Status | Item | Owner/next action |
|---|---|---|
| open | Decide read-write sharing policy for all users | In GUI, create/use an all-users group and share both NAS libraries read-write; internal public shares are currently read-only |
| open | Onboard POP Creations staff | Pre-create user in admin UI, add their Microsoft `social_auth_usersocialauth` link before first sign-in (auto-creation is off; see 2026-10-26 incident), then add them to the read-write group/share policy |
| optional | Move NAS compose/env staging out of `/tmp` | Use a persistent NAS path such as `/volume1/docker/seaf-cli/` if an operator wants easier recreates |
| optional | Pin `flrnnc/seafile-client` base image by digest | Improves reproducibility but requires a documented bump procedure |
| optional | Elasticsearch/full-text search | Requires RAM planning; current connection errors are expected because Elasticsearch is not deployed |
<!-- ansible-host-policy: managed rollout from u2giants/ansible -->
