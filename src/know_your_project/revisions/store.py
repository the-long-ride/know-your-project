import json
from datetime import datetime

import aiosqlite

from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId

from .models import FactVersion, Release


class SqliteRevisionStore:
    def __init__(self, path: str) -> None:
        self._path = path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS releases (
              project TEXT NOT NULL, release_id TEXT NOT NULL, tag TEXT NOT NULL,
              commit_sha TEXT NOT NULL, effective_at TEXT NOT NULL, predecessor TEXT,
              status TEXT NOT NULL DEFAULT 'pending', PRIMARY KEY(project, release_id));
            CREATE TABLE IF NOT EXISTS active_facts (
              project TEXT NOT NULL, scope TEXT NOT NULL, artifact_id TEXT NOT NULL,
              edge_uuid TEXT NOT NULL, fact_json TEXT NOT NULL,
              PRIMARY KEY(project, scope, artifact_id, edge_uuid));
            CREATE TABLE IF NOT EXISTS release_snapshots (
              project TEXT NOT NULL, release_id TEXT NOT NULL, edge_uuid TEXT NOT NULL,
              fact_json TEXT NOT NULL, PRIMARY KEY(project, release_id, edge_uuid));
            """)
            await db.commit()

    async def save_release(self, release: Release) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO releases VALUES(?,?,?,?,?,?,COALESCE((SELECT status FROM releases WHERE project=? AND release_id=?),'pending'))",
                (
                    str(release.project_id), str(release.release_id), release.tag,
                    release.commit_sha, release.effective_at.isoformat(),
                    str(release.predecessor) if release.predecessor else None,
                    str(release.project_id), str(release.release_id),
                ),
            )
            await db.commit()

    async def get_release(self, project: ProjectId, release_id: ReleaseId) -> Release | None:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT tag,commit_sha,effective_at,predecessor FROM releases WHERE project=? AND release_id=?",
                (str(project), str(release_id)),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return Release(
            project_id=project,
            release_id=release_id,
            tag=row[0],
            commit_sha=row[1],
            effective_at=datetime.fromisoformat(row[2]),
            predecessor=ReleaseId(row[3]) if row[3] else None,
        )

    async def get_latest_release(self, project: ProjectId) -> Release | None:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT release_id,tag,commit_sha,effective_at,predecessor FROM releases "
                "WHERE project=? AND status='ready' ORDER BY effective_at DESC LIMIT 1",
                (str(project),),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return Release(
            project_id=project,
            release_id=ReleaseId(row[0]),
            tag=row[1],
            commit_sha=row[2],
            effective_at=datetime.fromisoformat(row[3]),
            predecessor=ReleaseId(row[4]) if row[4] else None,
        )

    async def get_active_facts(
        self,
        project: ProjectId,
        artifact_id: ArtifactId,
        scope: str = "release",
    ) -> list[FactVersion]:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT fact_json FROM active_facts WHERE project=? AND scope=? AND artifact_id=?",
                (str(project), scope, str(artifact_id)),
            )
            rows = await cur.fetchall()
            return [FactVersion.model_validate(json.loads(row[0])) for row in rows]

    async def replace_active_facts(
        self,
        project: ProjectId,
        artifact_id: ArtifactId,
        facts: list[FactVersion],
        scope: str = "release",
    ) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "DELETE FROM active_facts WHERE project=? AND scope=? AND artifact_id=?",
                (str(project), scope, str(artifact_id)),
            )
            await db.executemany(
                "INSERT INTO active_facts(project,scope,artifact_id,edge_uuid,fact_json) VALUES(?,?,?,?,?)",
                [
                    (str(project), scope, str(artifact_id), f.edge_uuid, f.model_dump_json())
                    for f in facts
                ],
            )
            await db.commit()

    async def snapshot_release(self, project: ProjectId, release_id: ReleaseId) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "DELETE FROM release_snapshots WHERE project=? AND release_id=?",
                (str(project), str(release_id)),
            )
            cur = await db.execute(
                "SELECT edge_uuid,fact_json FROM active_facts WHERE project=? AND scope='release'",
                (str(project),),
            )
            rows = await cur.fetchall()
            await db.executemany(
                "INSERT INTO release_snapshots(project,release_id,edge_uuid,fact_json) VALUES(?,?,?,?)",
                [(str(project), str(release_id), row[0], row[1]) for row in rows],
            )
            await db.commit()

    async def get_release_snapshot(
        self, project: ProjectId, release_id: ReleaseId
    ) -> list[FactVersion]:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT fact_json FROM release_snapshots WHERE project=? AND release_id=?",
                (str(project), str(release_id)),
            )
            rows = await cur.fetchall()
        return [FactVersion.model_validate(json.loads(row[0])) for row in rows]

    async def set_release_status(
        self, project: ProjectId, release_id: ReleaseId, status: str
    ) -> None:
        if status not in {"pending", "indexing", "ready", "failed"}:
            raise ValueError(status)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE releases SET status=? WHERE project=? AND release_id=?",
                (status, str(project), str(release_id)),
            )
            await db.commit()
