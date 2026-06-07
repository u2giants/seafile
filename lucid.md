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

There are three realistic paths.

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

---

## Recommended Ranking for Our Use Case

1. LucidLink  
   Best user experience and collaboration filesystem, but expensive and proprietary.

2. Resilio Active Everywhere  
   Best fit for keeping Synology/local hardware involved and maintaining an exit path.

3. JuiceFS  
   Best open-source architectural alternative, but requires real engineering and support.

4. Mountain Duck  
   Useful for auxiliary cloud access, not the primary shared design filesystem.

5. Rclone  
   Excellent utility/migration tool, not safe for live multi-user design collaboration.

6. Synology Drive alone  
   Not sufficient for intercontinental live collaboration on large creative files.

---

## Current Decision

Do not immediately replace LucidLink with JuiceFS, Mountain Duck, or rclone.

Recommended next step:

Run a controlled POC comparing:

1. Resilio Active Everywhere.
2. JuiceFS.
3. LucidLink baseline, optionally with TeamCache for NYC.

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

- Test Resilio Active Everywhere first.

If the priority is open source and lowest software cost:

- Test JuiceFS, but treat it as an engineering project.

If the priority is cheap S3 access with a nice GUI:

- Mountain Duck is fine for side workflows, not the main shared drive.

If the priority is migration/backup scripting:

- Use rclone.
