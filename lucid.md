# LucidLink / JuiceFS / Resilio / Synology Strategy Notes

## Context

LucidLink is being evaluated for a distributed design workflow involving large creative files, remote workers, Synology NAS infrastructure, and a desire to avoid long-term vendor lock-in.

The main business problem is not simply cloud storage cost. The real requirement is a safe, fast, multi-user shared filesystem experience for large Adobe/CAD/design assets across geographic distance, especially between NYC and remote workers in Brazil.

The desired system must:

- Provide fast access to large creative files.
- Avoid simultaneous-edit conflicts and overwrite loops.
- Support practical file locking or equivalent workflow protection.
- Avoid permanent lock-in to LucidLink.
- Keep Synology NAS units in the loop so they can take over if LucidLink is abandoned.
- Be understandable and maintainable by the business, not just theoretically elegant.

---

## What LucidLink Actually Provides

LucidLink is expensive, but it is not merely marked-up S3.

The useful part of LucidLink is that it behaves like a global filesystem on top of object storage. It separates metadata/control from data blocks, streams file chunks on demand, caches locally, and coordinates access across users.

Important LucidLink strengths:

- Block-level, on-demand streaming.
- Local caching on client machines.
- Cloud/object-storage-backed filesystem.
- Distributed file locking.
- Desktop user experience that feels like a normal mounted drive.
- Managed service, support, and fewer moving parts for the customer.

The key point: LucidLink’s value is not just storage. It is the combination of metadata coordination, client software, caching behavior, locking, administration, support, and operational maturity.

---

## Assessment of the “Just Use Open Source + S3” Claim

The claim that LucidLink’s architecture can be replicated with open-source software, object storage, and a small VPS is directionally true but dangerously oversimplified.

Yes, the broad architecture can be copied:

- Metadata database/control plane.
- Object storage for file blocks.
- Local client mount.
- Local cache.
- On-demand block access.

But replicating the architecture does not automatically replicate the production experience.

Missing or risky areas include:

- File locking behavior across Windows/macOS and specific creative applications.
- Metadata database high availability.
- Client deployment and repair.
- Mount persistence after reboot.
- Cache configuration and troubleshooting.
- Permission model.
- Monitoring.
- Backups.
- Disaster recovery.
- User support.
- Failure behavior during WAN drops or database outages.

Conclusion: open-source alternatives may reduce subscription cost, but they shift operational complexity onto us.

---

## JuiceFS

JuiceFS is the closest open-source architectural analog to LucidLink.

JuiceFS uses:

- Object storage for file data.
- A metadata engine such as Redis, PostgreSQL, MySQL, TiKV, etc.
- A client that mounts the filesystem.
- Local caching.
- POSIX-oriented filesystem behavior.

Why JuiceFS is interesting:

- It is open source.
- It can use commodity S3-compatible storage such as Backblaze B2, IDrive e2, Wasabi, AWS S3, etc.
- It is architecturally similar to LucidLink.
- It can stream/cache file data rather than requiring full-file sync first.
- It is a serious technical candidate for a LucidLink-like backend.

Major concerns:

- It does not have a polished LucidLink-style desktop GUI.
- It is primarily CLI/admin-driven.
- End users would see a mounted drive only after IT scripts and config are working.
- Mount reliability on Windows/macOS must be engineered.
- Locking must be tested with the exact applications used by the design team.
- Metadata database uptime becomes mission-critical.
- A single Redis/Postgres instance on a cheap VPS is a single point of failure unless designed properly.
- Support burden falls on us.

GUI conclusion:

JuiceFS does not have a true end-user GUI like LucidLink, Dropbox, Google Drive, or Mountain Duck. It has admin/monitoring tools, and once mounted it appears in Finder/Explorer, but the setup and maintenance are technical.

Recommended role:

JuiceFS should be treated as a proof-of-concept engineering project, not an immediate production replacement.

A proper JuiceFS POC should include:

- Real object storage provider.
- Real metadata database.
- Windows and macOS clients.
- Local SSD cache.
- Startup/remount scripts.
- Real Adobe/CAD/design files.
- Intentional simultaneous-open and simultaneous-save tests.
- WAN interruption tests.
- Metadata backup/restore tests.
- Synology mirror/export process.

---

## Mountain Duck

Mountain Duck is a polished desktop client that can mount S3-compatible storage and other cloud/server protocols in Finder or Windows Explorer.

It has a better user experience than JuiceFS for non-technical users.

However, Mountain Duck should not be considered a true LucidLink replacement for our main production design filesystem.

Good uses:

- Browsing cloud archives.
- Accessing isolated freelancer/vendor folders.
- Occasional remote file access.
- One-user-at-a-time workflows.
- Utility access to S3 buckets.

Poor uses:

- Multi-user live production collaboration.
- Adobe/CAD active project folders.
- Workflows requiring strong cross-user locking.
- Preventing last-writer-wins conflicts.
- Replacing LucidLink as the global working drive.

Conclusion:

Mountain Duck is useful, but not the main solution for our remote design team.

---

## Rclone

Rclone is excellent for:

- Migration.
- Backup.
- Copying data between storage providers.
- Admin workflows.
- Mounting cloud storage for technical use.

Rclone mount with VFS cache mode can make a cloud bucket appear like a drive, but it should not be used as the live collaborative filesystem for designers.

Major issue:

- It does not provide the global file-locking and collaborative safety model needed for simultaneous creative work.

Conclusion:

Rclone is a utility tool, not a production LucidLink replacement for this use case.

---

## Seafile / SeaDrive

Seafile deserves a separate role in this plan because it is already running and it fits the WFH macOS reality better than Resilio's documented file-locking model.

Seafile should not be treated as a perfect LucidLink clone. It is better understood as the WAN transport and local-cache layer that PopDAM can control.

Recommended Seafile role:

- Data transport plane for WFH designers.
- Local cache/on-demand file access through SeaDrive, especially on macOS.
- Background block-oriented sync so PopDAM Helper does not need to move every large file synchronously from NYC over HTTP.
- Remote access layer for designers who should not mount the NYC NAS directly over SMB/Tailscale.
- Server-side hub that can sync or export back to Synology so owned NAS infrastructure remains in the loop.

Why this is strategically attractive:

- It uses infrastructure we already have instead of introducing another major platform first.
- SeaDrive gives macOS users a Finder-visible workspace without requiring a full 20 TB local sync.
- Seafile Professional supports file locking in the web app and desktop clients; its user manual describes lock/unlock from Finder on macOS and read-only behavior when another user holds a lock.
- PopDAM can use Seafile as "muscle" while keeping checkout state, workflow policy, and audit history in Supabase.

Important limitation:

Seafile's automatic locking documentation is strongest for Microsoft Office files. Adobe PSD/AI workflows should not assume automatic application-level locking will be enough. For Adobe files, PopDAM should explicitly acquire a PopDAM checkout before allowing edit, and the Helper should explicitly lock or gate the file workflow.

The better architecture is:

```
PopDAM / Supabase = brain, checkout state, audit, permissions
POP DAM Helper    = user workflow, open/check-in/check-out, local orchestration
Seafile / SeaDrive = WAN transport, local cache, background sync
Synology NAS      = owned storage, backup/mirror/emergency cutover
```

In this model, PopDAM Helper should prefer the local SeaDrive cache when it is fresh and available. If a file is not hydrated locally, Helper should ask SeaDrive/Seafile to hydrate it or download through Seafile, rather than pulling directly from NYC over slow SMB or a synchronous NAS HTTP path. Check-in should similarly hand the completed file to Seafile's sync/cache layer while PopDAM tracks the checkout lifecycle and final verification.

This does not remove the need for PopDAM locks. It changes who moves the bytes.

Suggested PopDAM + Seafile workflow:

1. User clicks **Check Out & Open** in PopDAM.
2. PopDAM creates an atomic `asset_checkouts` row in Supabase.
3. Helper maps the PopDAM asset path to the corresponding SeaDrive path.
4. Helper confirms the local SeaDrive file is current or triggers hydration.
5. Helper copies the current file into a private local workspace or opens a controlled working copy.
6. User edits locally.
7. Helper snapshots the result and checks it in.
8. Seafile handles WAN transfer in the background.
9. PopDAM verifies server-side state and releases the checkout only after the new version is safely present.

Where Seafile should be used:

- WFH macOS designers' day-to-day access path.
- Local cache/hydration for large design files.
- Background WAN transfer.
- PopDAM Helper integration.
- Synology mirror/export/cutover support.

Where Seafile should not be the only safety mechanism:

- It should not be trusted alone to prevent Adobe overwrite conflicts.
- It should not replace PopDAM's checkout state machine.
- It should not leave designers free to edit directly in shared folders without PopDAM workflow enforcement.

Sources checked:

- Seafile file locking user manual: https://help.seafile.com/sharing_collaboration/file_locking/
- SeaDrive for macOS manual: https://help.seafile.com/drive_client/drive_client_for_macos/

---

## Resilio Active Everywhere

Resilio Active Everywhere may be strategically more aligned with our business goals than JuiceFS, even though JuiceFS is more architecturally similar to LucidLink.

Reason:

Our goal is not just to copy LucidLink. Our goal is to avoid lock-in and keep Synology/local NAS infrastructure able to take over.

Resilio is sync-oriented rather than stream-first. That means it may require more local storage and may not feel exactly like LucidLink. But it keeps real copies of files on owned infrastructure and endpoints, which fits the “NASes stay hot” requirement.

Potential strengths:

- Better fit for owned-hardware continuity.
- Can keep Synology/NAS infrastructure involved.
- May provide better exit path from LucidLink.
- Designed for distributed file synchronization.
- Paid platform includes file-locking-oriented features.
- More practical than DIY open-source for some production environments.

Tradeoffs:

- Not the same as a global object-backed filesystem.
- Initial sync can be heavier.
- Remote users may need more local disk.
- Still needs careful file-locking tests.
- Still needs workflow discipline.
- Not necessarily cheaper than all DIY options, but may be much cheaper than LucidLink at scale.

Recommended role:

Resilio Active Everywhere should be tested first if the top priority is business continuity and keeping Synology NASes ready to take over.

MacOS file-locking reality:

After checking Resilio's current documentation, Resilio should not be assumed to provide direct file-lock enforcement on WFH macOS workstations. Their file-locking documentation lists the file-locking feature's supported platform as Windows x64 10 and newer. It also says Windows, Linux, and macOS Agents can take the Lock Server role, but agents on other operating systems can participate without imposing locks on locally opened files.

That distinction matters. A macOS agent that can participate in a job or act as a lock server is not the same as a macOS designer workstation that enforces "this PSD is read-only because someone else has it open" inside Finder/Adobe workflows.

Because all WFH remote designers are on macOS, Resilio should be demoted from "test first for WFH editing" to "test only for server/NAS replication, cache gateways, or site-to-site continuity unless the vendor confirms macOS lock enforcement in writing and demonstrates it with Adobe files."

Where Resilio may still fit:

- NAS-to-NAS replication.
- NYC to branch-office server replication.
- Server/cache gateway synchronization.
- Keeping owned infrastructure hot as an exit path.
- Moving large datasets between storage systems faster than ordinary sync tools.

Where Resilio should not be assumed to fit:

- Direct WFH macOS designer editing with lock enforcement.
- Replacing PopDAM checkout/check-in.
- Replacing Seafile/SeaDrive as the primary macOS user-facing cache layer unless a vendor-led macOS POC proves lock enforcement.

Sources checked:

- Resilio file locking documentation: https://www.resilio.com/documentation/content/advanced-configuration/mc-and-jobs/file_locking/
- Resilio Active Everywhere file-locking feature page: https://www.resilio.com/active-everywhere/features/file-locking/
- Resilio roadmap noting macOS kernel-extension/user-experience work: https://helpdesk.resilio.com/hc/en-us/articles/41088800035475-Resilio-Active-Everywhere-2024-2025-Roadmap

---

## Synology Drive

Synology Drive alone is not recommended as the primary intercontinental live collaboration layer for Adobe/CAD/design files.

Reasons:

- Prior experience already showed sync/version/friction problems.
- Synology Drive conflict behavior is not equivalent to LucidLink’s distributed filesystem locking.
- NAS-to-NAS and client sync can produce conflict files and version mismatch issues.
- Large creative files across continents are a worst-case scenario for ordinary sync tools.

Recommended Synology role:

- Local office file server.
- Backup destination.
- Read-only or nearline mirror.
- Emergency cutover target.
- Snapshot/replication target.
- Hyper Backup target.
- Resilio endpoint.
- Data ownership layer.

Do not rely on Synology Drive alone as the main Brazil/NYC production collaboration system.

---

## LucidLink TeamCache

TeamCache is an on-site shared cache layer for LucidLink.

Instead of each workstation independently downloading the same file blocks from LucidLink/cloud storage, TeamCache lets one local site cache data once and serve repeated access over the local LAN.

Normal LucidLink pattern:

- Workstation 1 pulls from LucidLink/cloud.
- Workstation 2 pulls same blocks from LucidLink/cloud.
- Workstation 3 pulls same blocks from LucidLink/cloud.

With TeamCache:

- Workstations talk to a local TeamCache node.
- TeamCache fetches uncached data from LucidLink/cloud.
- Repeated access comes from local cache over LAN.

Useful for:

- NYC office with multiple users touching the same files.
- Branch offices with many users.
- Reducing duplicate internet downloads.
- Improving office user performance.
- Making LucidLink feel more local at a physical site.

Not useful for:

- Replacing LucidLink.
- Reducing lock-in.
- Making Synology the source of truth.
- Helping individual WFH users much unless they share a site-level cache.
- Eliminating LucidLink subscription cost.

Conclusion:

TeamCache is a performance accelerator for LucidLink, not an exit strategy.

---

## TeamCache Hardware

LucidLink TeamCache appears to be software installed on a local server or VM, not a specific branded hardware appliance.

Hardware should be thought of as a high-speed local cache node.

Recommended hardware profile for NYC:

Minimum serious version:

- Dedicated server, workstation, or VM host.
- Modern 8-core CPU.
- 32 GB RAM.
- Dedicated NVMe cache storage.
- 10GbE.
- UPS-backed power.
- Separate OS disk and cache volume.

Better version:

- 12-16 core CPU.
- 64 GB RAM.
- 2-4 enterprise NVMe SSDs.
- 10GbE or 25GbE.
- Stable Linux or Windows Server.
- Monitoring.
- UPS.

Avoid:

- HDD cache.
- 1GbE bottleneck.
- Old Synology units as the cache node.
- Cheap consumer SSDs for heavy multi-user cache.
- Treating cache storage as authoritative data.

Important:

TeamCache cache is not the master data. It is disposable/rebuildable cache. The authoritative data remains in LucidLink/object storage.

---

## Recommended Architecture Direction

There are now four realistic paths.

### Path A: Stay with LucidLink, reduce risk

Use LucidLink for the production workspace, but avoid lock-in by keeping Synology mirrors and backup/export workflows active.

Add TeamCache only if office performance or bandwidth becomes a problem.

This gives the best user experience but does not solve subscription cost or vendor lock-in by itself.

Required lock-in mitigation:

- Regular export/mirror from LucidLink to Synology.
- Synology snapshots.
- Tested restore process.
- Documented emergency cutover process.
- Periodic dry-run of “operate from Synology” mode.
- Avoid using LucidLink-only workflows that cannot be replicated elsewhere.

### Path B: Test Resilio Active Everywhere first

This is likely the best alternative if the priority is:

- Keep Synology in the loop.
- Avoid LucidLink lock-in.
- Maintain local copies.
- Have owned infrastructure that can take over.

Test Resilio with:

- NYC primary NAS/server.
- Secondary NYC/Brooklyn NAS.
- Brazil workstation(s).
- File locking enabled.
- Real Adobe/CAD/design test files.
- Simultaneous edit tests.
- WAN outage/reconnect tests.
- Conflict behavior tests.
- Local disk usage tests.

MacOS caveat:

This path is no longer the recommended first test for WFH designer workstations unless Resilio confirms and demonstrates macOS lock enforcement. It remains relevant for NAS/server replication and business-continuity testing.

### Path C: Test JuiceFS as the open-source LucidLink-like option

This is the best open-source technical experiment.

Test JuiceFS only if we are willing to own:

- Metadata database operations.
- Client scripts.
- Monitoring.
- Cache tuning.
- Backups.
- Restore processes.
- User support.
- Locking validation.

A JuiceFS production setup would need:

- Highly available or at least well-backed-up metadata engine.
- Object storage in a region with good latency to NYC and Brazil.
- Local SSD/NVMe cache on each workstation.
- Automated mount scripts.
- Clear support/runbook.
- Synology mirror/export process.
- Regular restore testing.

### Path D: Use Seafile as transport, PopDAM as workflow control

This is now the most practical near-term path because Seafile is already present and WFH designers are on macOS.

Use:

- Seafile/SeaDrive for file transport, local hydration, and background sync.
- PopDAM/Supabase for checkout locks, audit, file state, and permissions.
- POP DAM Helper for opening controlled working copies and check-in/check-out UX.
- Synology as backup/mirror/emergency source of truth.
- Optional Resilio only for server/NAS replication if it proves valuable.

This path avoids asking PopDAM to synchronously download giant files from NYC and avoids depending on Resilio macOS file-lock enforcement that is not clearly supported by the current documentation.

---

## Recommended Ranking for Our Use Case

1. PopDAM + Seafile / SeaDrive  
   Best near-term fit if LucidLink is out of the question and WFH users are on macOS. Seafile moves/cache files; PopDAM controls workflow and locks.

2. LucidLink  
   Best user experience and collaboration filesystem, but expensive and proprietary.

3. Resilio Active Everywhere  
   Best fit for keeping Synology/local hardware involved and maintaining an exit path, but not currently proven as a direct macOS WFH locking solution.

4. JuiceFS  
   Best open-source architectural alternative, but requires real engineering and support.

5. Mountain Duck  
   Useful for auxiliary cloud access, not the primary shared design filesystem.

6. Rclone  
   Excellent utility/migration tool, not safe for live multi-user design collaboration.

7. Synology Drive alone  
   Not sufficient for intercontinental live collaboration on large creative files.

---

## Current Decision

Do not immediately replace LucidLink with JuiceFS, Mountain Duck, rclone, or Resilio as the direct WFH macOS editing client.

Recommended next step:

Run a controlled POC comparing:

1. PopDAM Helper + Seafile/SeaDrive.
2. Resilio Active Everywhere for NAS/server replication, not as the first macOS locking answer.
3. JuiceFS only if we are willing to own a filesystem engineering project.
4. LucidLink baseline only for reference, since cost rules it out.

The POC must use real files, real users, and deliberate conflict tests.

The final decision should be based on:

- Performance with real design files.
- File-locking behavior.
- Conflict behavior.
- Recovery behavior.
- User friction.
- Admin burden.
- Synology continuity.
- Cost over 2-3 years.
- Ease of leaving the platform.

---

## Practical Rule

If the priority is the best possible remote design experience:

- LucidLink remains the safest option.

If the priority is avoiding LucidLink lock-in while keeping NASes ready:

- Use Seafile with PopDAM workflow control first; test Resilio for NAS/server replication second.

If the priority is direct WFH macOS designer workflow:

- Prefer PopDAM Helper + Seafile/SeaDrive over Resilio unless Resilio proves macOS lock enforcement with Adobe files.

If the priority is open source and lowest software cost:

- Test JuiceFS, but treat it as an engineering project.

If the priority is cheap S3 access with a nice GUI:

- Mountain Duck is fine for side workflows, not the main shared drive.

If the priority is migration/backup scripting:

- Use rclone.
