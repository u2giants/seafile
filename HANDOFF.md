# Handoff

This file describes work in progress as of 2026-05-08. Delete it when the Synology seaf-cli containers are deployed and confirmed syncing.

## What Was Being Built

Deploying seaf-cli Docker containers on the NYC Synology NAS devices to push the 28TB file library to the Seafile Pro server at `seafile.designflow.app`.

## What Is Fully Done

**Seafile Pro server (seafile.designflow.app):**
- Running on Linode VPS (172.233.14.233), Ubuntu 24.04
- Seafile Pro 13.0, TLS via Let's Encrypt, Cloudflare DNS-only A record
- S3 storage configured: Linode Object Storage, São Paulo (br-gru-1), 3 buckets
- Google OAuth SSO live (u2giants@gmail.com via Google, plus albert@popcre.com local)
- NAS sync machine account: nas-sync@popcre.com (password in CREDENTIALS.txt)
- Libraries created: Active Projects, Assets, Seasonal (UUIDs in CREDENTIALS.txt and synology-seaf-cli/README.md)
- Daily MySQL backup cron, Docker auto-start on boot

**Synology seaf-cli config:**
- `synology-seaf-cli/docker-compose.yml` written with correct UUIDs, pre-filled with nas-sync@popcre.com
- `synology-seaf-cli/.env.example` created
- `synology-seaf-cli/README.md` with setup instructions

**GitHub repo:** https://github.com/u2giants/seafile — all of the above committed.

## What Is Partially Done

**Synology MCP connection:** A custom MCP server at `https://nas-mcp.designflow.app/mcp` was configured in `~/.claude/settings.json` on the VPS using HTTP transport with a bearer token. This allows Claude Code to interact with the Synology NAS directly. However, MCP servers are loaded at session startup — the config was written during this session, so the tools are not yet active. They will be available in the **next** Claude Code session.

Current entry in `~/.claude/settings.json`:
```json
"mcpServers": {
  "synology-monitor": {
    "type": "http",
    "url": "https://nas-mcp.designflow.app/mcp",
    "headers": {
      "Authorization": "Bearer 14cde11e584136b15306c03d160ce9536da4f87f82d74c6d728a6c8cb6dd2122"
    }
  }
}
```

## What Has Not Been Started

1. **Actually deploying seaf-cli on the Synology** — the compose file is ready but needs to be transferred to and started on the Synology hardware
2. **Designer user accounts** — 8 São Paulo designers not yet created. Easiest path: send them the URL and have them sign in via Google SSO; accounts auto-create on first login
3. **Sharing libraries with designers** — once accounts exist, share Active Projects/Assets/Seasonal with each designer (Read/Write)
4. **Elasticsearch** — not deployed, intentionally (RAM constraint). Not blocking anything

## Decisions Made and Why

**nas-sync@popcre.com, not @popcreations.com** — Albert corrected the domain during this session. The company's email domain is popcre.com, not popcreations.com.

**S3 with 3 separate buckets** — Seafile Pro requires distinct bucket names for blocks, commits, and fs stores — it refuses to start otherwise. Only `seafile-s3` existed; `seafile-s3-commits` and `seafile-s3-fs` were created via the Linode S3 API during this session.

**S3 in São Paulo (br-gru-1)** — Bucket already existed there (Albert created it). Same region as designers = fast reads.

**Cloudflare proxy stays off** — Seafile's sync protocol (binary, port 8082 internally) breaks through Cloudflare's HTTP proxy. Never enable the orange cloud on this DNS record.

**Elasticsearch not deployed** — 4GB RAM server; Elasticsearch alone needs ~2GB, leaving inadequate headroom. vm.max_map_count is already set for when this changes.

**albert@popcre.com as second admin** — Albert wanted a local-password fallback that doesn't depend on Google SSO. Created as a separate admin account.

## Dead Ends

**Cloudflare MCP for DNS** — The claude.ai Cloudflare Developer Platform MCP has no DNS tools. DNS record creation was done via direct curl to the Cloudflare API using a bearer token Albert provided. There was also a pre-existing proxied A record pointing to 92.113.32.78 that had to be deleted first.

**docker.seadrive.org image tag** — The Seafile manual says to use `docker.seadrive.org/seafileltd/seafile-pro-mc:13.0-latest` but that tag does not exist on the private registry. The 13.0 image is on Docker Hub. The `latest` tag on docker.seadrive.org is a different (newer) build.

**S3 with single bucket** — First attempt used `seafile-s3` for all three storage types. Seafile logs "Commits, fs and blocks should use different buckets" and refuses to start. Required creating two additional buckets.

**CREATE_NAS_SYNC_ACCOUNT.sh first attempt** — Script used PUT method and wrong email (@popcreations.com). User creation failed silently, then the account was deleted before libraries were transferred, orphaning them. Libraries had to be recreated. Script has been fixed in the repo.

## Exact Next Action

1. Start a new Claude Code session on the VPS (the Synology MCP tools will now be available)
2. Explore what tools the `synology-monitor` MCP exposes
3. Use those tools (or SSH) to deploy `synology-seaf-cli/docker-compose.yml` on the Synology
4. NAS sync password is in `/opt/seafile/CREDENTIALS.txt`
5. Verify containers start and begin syncing

## Known Risks and Unknowns

- **Unknown: actual NAS folder paths.** The compose file assumes `/volume1/ActiveProjects`, `/volume1/Assets`, `/volume1/Seasonal`. The real paths on the Synology may differ. Confirm before deploying.
- **Unknown: seaf-cli Docker image compatibility.** The compose file uses `seafileltd/seaf-cli:latest`. Confirm this image exists and is compatible with Seafile Pro 13.0 before deploying.
- **Risk: initial 28TB sync will be slow.** Leave containers running. Do not restart or redeploy during initial sync — seaf-cli state is in Docker named volumes and would be lost.
- **Risk: NAS outbound bandwidth.** Pushing 28TB from NYC to São Paulo S3 will consume significant bandwidth. Coordinate with Albert on timing.
- **Unknown: Synology MCP tool capabilities.** The MCP at nas-mcp.designflow.app has not been interrogated yet — its actual tools are unknown. It may support direct container management or it may only provide monitoring.
