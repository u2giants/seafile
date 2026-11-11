---
summary: Completed November 5, 2026 license recovery plan: proof, backups, atomic 11-user license replacement, restart, verification, publication. Do not rerun it.
kind: plan
status: done
read-when: license-capacity questions or a similar recovery
---

# STATUS — completed November 5, 2026

All six steps are complete. **Historical execution evidence: do not redo the replacement.** The effective installed license now has SHA256 `dbc1940bf8ed8b430a9cbedae06419c25353061beaeb105b7cdc65f258fd0a23`, capacity 11, expiration October 26, 2027. The original ten-user hash below is a historical input and deliberately no longer matches the live file.

| Step | Status | Evidence |
|---|---|---|
| 1. Prove target/count/guards and back up databases | done — November 5, 2026 | Verified seafile-br, exact mount/hash, 11 active accounts and disabled signup; protected transactional backup recorded on issue #19. |
| 2. Back up and atomically replace effective license | done — November 5, 2026 | Pinned replacement hash installed and checked; original license preserved root-only. |
| 3. Restart only Seafile | done — November 5, 2026 | Native account service recovered with capacity 11; other services and NAS configuration unchanged. |
| 4. Verify actual account/library access | done — November 5, 2026 | Native count 11, original admin/Microsoft binding, account-info, all five libraries and bounded root listing passed; login page 200 and Microsoft redirect correct. |
| 5. Evaluate failure containment | done — November 5, 2026 | Native server accepted the license; rollback was not needed or exercised. Backups remain available. |
| 6. Publish operating knowledge | done — November 5, 2026 | Seafile PR #20 and albert-standards PR #7 merged; issue #19 closed. |

Start here in a fresh session: there is no remaining implementation. Read the closed [recovery record](https://github.com/u2giants/seafile/issues/19) for proofs and the [configuration guide](configuration.md) for current operation. A new incident needs fresh target/capacity checks, not a replay of this plan.

Verification boundary: no personal Microsoft browser session was impersonated or claimed as tested. The owner explicitly retired the extra sign-in-confirmation request after the above live proofs; it is not an open task. PopDAM's separate source-history checks belong to its existing application issue and are not part of this completed license recovery.

The rationale and exact pre-recovery inputs below are retained as history. Recorded shell syntax and existing Python suites passed (45 sync checks, 44 panel checks). Final exact-action GLM security approval and the successful production gate are recorded on issue #19. Nothing is pending or blocked in this workstream.

---

# Seafile 11-user license recovery — issue u2giants/seafile#19

Request: owner attached the replacement Seafile license and requested installation in this chat. Keep all 11 active accounts, including NAS sync. No schema/data/account/SSO setting changes. This committed plan is the production-action review subject, not a request to review the historical CI change. Codex owns execution and follow-up; retire this plan into the incident record after completion.

Exact production target: hostname seafile-br; container seafile; /opt/seafile-data bind-mounted to /shared. Container /opt/seafile/seafile-license.txt resolves to /shared/seafile/seafile-license.txt, host /opt/seafile-data/seafile/seafile-license.txt. Pre-recovery installed SHA256: 9d3e0b2079d4e9000a1a796feb21a7b5e4228a4a978b39b61c5f968e89c57561. It permits 10 users; all 11 active accounts cause repeated native-backend rejection and OAuth callback ConnectionRefusedError. Public host seafile.designflow.app.

Owner-supplied replacement: /home/ai/.codex/attachments/3f37846f-552e-4e74-804e-f7e363f9f896/seafile-license.txt; exact SHA256 dbc1940bf8ed8b430a9cbedae06419c25353061beaeb105b7cdc65f258fd0a23; 1251 bytes; MaxUsers="11"; expires October 26, 2027. Never show license bytes or put them in Git/review snapshots. Metadata only here.

Requested exact resource/action approval:
1. Re-prove hostname, mount, destination hash and replacement hash; verify active count exactly 11 through SELECT COUNT(*) FROM ccnet_db.EmailUser WHERE is_active=1 immediately before swap/restart. Confirm REMOTE_USER_CREATE_UNKNOWN_USER=False and ENABLE_SIGNUP=False remain set. Take a fresh root-only dump of ccnet_db and seahub_db before replacement (MYSQL_PWD inside the database container, protected pipe/file only; no credentials in argv). Refuse if any differs. Preserve unrelated /shared/seafile-license.txt (old 9-user copy).
2. With root privileges, create a root-only timestamped backup of the exact installed file beside it (mode 0600). Write the replacement through a new exclusive 0600 temporary file in the same destination directory; flush/fsync; preserve destination ownership and mode; os.replace atomically to the exact destination. Verify destination matches the replacement hash; license bytes move only through protected files. Keep backup for recovery.
3. docker restart seafile (existing documented app operation, no host/OS mutation). New capacity is 11 and active count <=11 BEFORE restart. Bounded wait for application availability. Do not restart other containers, touch NAS, edit upstream code, alter accounts, or purchase anything.
4. Verify running backend accepts local native RPC, detects capacity 11, resolves existing Albert account, and active count remains 11. Verify public login and Microsoft authorization redirect, then existing token-authenticated account/library API reads (NAS sync account's pre-existing token from DB passed only inside protected Python process; never log credentials or tokens). Check new logs for license/RPC failures. Do not impersonate Microsoft user or claim human Microsoft sign-in proven without actual browser session. Synthetic exercise of OAuth account lookup is allowed, no authentication bypass.
5. If the new license fails validation, restore the backed-up exact 10-user bytes atomically, but DO NOT restart into capacity 10 with 11 active accounts: that is known nonworking. Preserve all accounts, record blocked recovery; ask vendor for valid replacement. Restoration is containment, not successful recovery. No account suspension authorized.
6. Record outcome and any remaining real Microsoft-login proof on SAME issue #19; update AGENTS.md restart threshold/expiry, docs/configuration.md, docs/architecture.md, docs/development.md, the start-helper effective license path, and applicable albert-standards in this session to reflect installed capacity if successful. Review cannot read live secrets; exact metadata and verification commands were read-only checked by implementing Codex.

The reviewer must give an explicit APPROVE or REJECT for the exact license replacement plus seafile-only restart above, tied to the current Git HEAD. Production gate must pass with that report before steps 2–3. No purchase, identity merge, secret rotation, infrastructure change or license enforcement bypass authorized.

Approval requested explicitly: conditional APPROVE for replacing only the exact effective license on seafile-br with the exact owner-provided SHA256 above, after the specified fresh identity/count/backup proofs, then restarting only container seafile and performing read-only verification. A generic CI-only approval does not authorize this action. State explicitly whether this exact production action is approved. Native license signature validation occurs on server startup; if invalid, restore original bytes and report blocked; do not suspend accounts, bypass licensing, or claim service restored. The owner-provided app attachment is retained with mode 0600 for recovery, not deleted by this task.
