# Operations Runbook

This document is a verification checklist to confirm the stack is production-ready for
personal use. Work through each section after initial setup and after any significant
change to the host machine (OS upgrade, Docker Desktop update, etc.).

All commands assume you are in the `video_journal_be` repository directory.

---

## 1. Reboot Persistence Verification

Confirms that the full stack — containers and data — survives a Mac reboot without any
manual intervention.

**Steps:**

1. Create at least one clip, one soundtrack, and one compilation via the app UI
   (http://localhost:3000). Note their names or counts so you can verify them after
   reboot.
2. Enable Docker Desktop start-on-login:
   **Docker Desktop -> Settings -> General -> "Start Docker Desktop when you sign in."**
3. Fully reboot the Mac (Apple menu -> Restart).
4. After logging back in, wait approximately 30 seconds for Docker Desktop and the
   containers to come up, then run:
   ```bash
   docker compose ps
   ```
   Both `backend` and `frontend` should show `Up`.
5. Open http://localhost:3000 and confirm all previously created clips, soundtracks, and
   compilations are still present and playable.

**Result:**

- [ ] Pass
- [ ] Fail

---

## 2. Non-Destructive Restart Verification

Confirms that `docker compose down` followed by `docker compose up -d` does not touch
the bind-mounted data directories.

**Steps:**

1. Note the current count of clips, soundtracks, and compilations shown in the app UI.
2. Stop and remove the containers:
   ```bash
   docker compose down
   ```
   Confirm the output shows containers being stopped and removed. The `./data`,
   `./media`, and `./outputs` directories on the host are **not** mentioned — they are
   bind mounts and are left untouched by `down`.
3. Start the stack again:
   ```bash
   docker compose up -d
   ```
4. Confirm the backend applied migrations cleanly (should report no new migrations on a
   clean restart):
   ```bash
   docker compose logs backend | grep -i migration
   ```
5. Open http://localhost:3000 and confirm all clips, soundtracks, and compilations are
   still present and unchanged from step 1.

**Result:**

- [ ] Pass
- [ ] Fail

---

## 3. `docker compose down -v` Warning

> **Caution: do not use this flag without understanding its effect.**

The `-v` flag tells Compose to remove **named volumes** declared under the `volumes:`
key in `docker-compose.yml`. This project stores all its data in **bind mounts**
(`./data`, `./media`, `./outputs`) rather than named volumes, so `-v` would not delete
application data in the current configuration.

However:

- If you ever add a named volume to `docker-compose.yml`, running `docker compose down -v`
  will destroy it.
- Before using `-v` for any reason, verify your `docker-compose.yml` has no named volumes
  containing data you care about.

**Never run `docker compose down -v` expecting all data to survive without first checking
your compose file.**

---

## 4. Backup Verification (Optional Manual Test)

Confirms the backup procedure produces a complete, non-zero archive. Recommended the
first time you set up the stack and after any change to the data directory layout.

**Steps:**

1. Stop the containers so SQLite flushes the WAL and the database is in a consistent
   state:
   ```bash
   docker compose down
   ```
2. Create the backup archive:
   ```bash
   tar czf journal-backup-test-$(date +%F).tgz data media outputs
   ```
3. Restart the stack:
   ```bash
   docker compose up -d
   ```
4. Confirm the archive exists and is non-zero in size:
   ```bash
   ls -lh journal-backup-test-*.tgz
   ```
   The size will vary depending on how much content you have, but it must not be `0`.

**Result:**

- [ ] Pass
- [ ] Fail

---

## Summary Checklist

Use this after completing all sections above:

- [ ] Reboot persistence confirmed (section 1)
- [ ] Non-destructive restart confirmed (section 2)
- [ ] Backup procedure tested (section 4)
