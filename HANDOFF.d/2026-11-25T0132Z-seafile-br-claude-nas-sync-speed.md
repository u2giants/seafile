---
issue: 34
status: OPEN
owner: claude/seafile-edgesynology-speed-test-c6850f
---
# NAS-to-server Seafile sync speed

## 0. Business decisions only the owner can make
Blocking: **Build a relay VM on the NAS?** A small Linux VM on edgesynology1 would carry the NAS's Seafile traffic using modern network tuning, aiming to lift single-file uploads from ~48 Mbps toward ~160 Mbps. Recommendation: yes, as a reversible trial. Blocks step 2.
Recoverable: **Colombia/São Paulo home-user slowness** — ask one remote user for a speed-test screenshot (speedtest.net) from their home, so the next session can tell if their own line is the limit. Recommendation: send it.
Already settled — do NOT re-ask: moving the server to Miami is rejected (2026-11-25, owner: it "defeats the whole purpose of a server serving large files to people working from home in sao paulo"); AI admin on the NAS will not be restored (2026-10-26); NAS Tailscale update done by owner (2026-11-25).
Next session: put both questions to Albert in ONE message before starting.

## 1. What this application is
Seafile file-sync server for POP Creations at https://seafile.designflow.app, on a Linode VPS in São Paulo (hostname seafile-br). The NYC office NAS (Synology, edgesynology1) syncs libraries to it through a seaf-cli container; remote staff (São Paulo, Colombia) use Seafile clients. Repo: https://github.com/u2giants/seafile — architecture: https://github.com/u2giants/seafile/blob/main/docs/architecture.md

## 2. Goal and trigger
Albert found NAS↔server transfers slow and asked to speed them up; remote users also report slowness.

## 3. Current state (2026-11-25)
- Measurements and dead ends recorded in https://github.com/u2giants/seafile/blob/main/docs/idiosyncrasies.md (section "NAS-to-server sync is capped per connection").
- Server is exactly as before the session: CUBIC, fq_codel, no extra firewall rules (BBR and a UFW 41641/udp rule were applied then reverted).
- NAS Tailscale 1.104.7, direct connection to the VPS confirmed.
- Nothing else deployed. Relay VM not started.

## 4. What did NOT work
- Tailscale SSH speed test (20 Mbps): misleading — it went through a DERP relay; Seafile does not use Tailscale.
- Opening UFW 41641/udp on the VPS: did not produce a direct Tailscale link; the old NAS client (1.58.2) advertised no endpoints. The owner's NAS update fixed it. Rule was removed.
- BBR on the VPS: server-to-NAS stayed 102–125 Mbps (was 121); the slow direction is NAS-sending. AI reviewer (codex diff-review) REJECTED twice: host change from this repo, unproven benefit. Reverted.
- NAS BBR: impossible — DSM kernel 4.4.302+ offers only cubic/reno.
- Owner-supplied ideas checked: seaf-cli 1.3.2 has no thread settings (strings show only upload_limit/download_limit); Go fileserver (use_go_fileserver = true) ignores worker_threads; Caddy (caddy-docker-proxy labels in https://github.com/u2giants/seafile/blob/main/seafile-server/seafile-server.yml) streams by default; HTTP/2 and h3 already advertised.
- Running seaf-cli itself inside a VM: rejected — files reach a VM over a network share where instant change detection (inotify) does not work.

## 5. Key findings
Per-connection cap from ~110 ms RTT + CUBIC loss recovery on the NAS sender; TCP buffers (rmem max 6 MB, wmem max 4 MB both ends) are ample. Parallel streams scale (4 → 160 Mbps). NAS: Xeon D-1527, 8 threads, 31 GB RAM — Synology VMM capable.

## 6. Exact next steps
1. Ask the §0 questions. Done when Albert answers.
2. If yes: create an Ubuntu LTS VM in Synology VMM (needs owner to install VMM — no AI NAS admin), enable BBR + fq, run a small HTTP proxy (e.g. tinyproxy) reachable only from the NAS. Done when `sysctl net.ipv4.tcp_congestion_control` in the VM shows bbr.
3. Point seaf-cli at the proxy (seaf-cli daemon proxy config: use_proxy/proxy_type/proxy_addr/proxy_port — verify exact keys in the image first) via repo change to https://github.com/u2giants/seafile/blob/main/synology-seaf-cli/ and PR. Done when a sync log shows traffic via the proxy.
4. Re-run the single-stream 500 MB upload test (method: temporary library via api2, upload link, curl from NAS — see §8). Done when upload is clearly above 48 Mbps; tick live proof on issue #34.

## 7. Constraints
PR to main only; AI reviewer APPROVE before production host changes (and before applying — this session applied BBR early, a slip); the VPS host layer is NOT in u2giants/ansible (that inventory is hetz only) but the reviewer still objected to host config living here — settle placement with the reviewer first. NAS docker/VMM actions are owner-run.

## 8. Access
VPS: Claude runs on it as ai (sudo). NAS: `ssh edge1` (ai, no sudo). Seafile admin creds: /opt/seafile/CREDENTIALS.txt on the VPS (root-only) and 1Password vault vibe_coding. Speed test: get a token from /api2/auth-token/, create a temp library, request /upload-link/, curl -F from the NAS, delete the library after.

## 9. Risks
A proxy adds a hop and a failure point for all NAS sync; keep it reversible. VPS move to Miami rejected 2026-11-25.
