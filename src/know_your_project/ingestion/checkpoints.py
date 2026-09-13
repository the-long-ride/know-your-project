import aiosqlite


class SqliteCheckpointStore:
    def __init__(self, path: str) -> None:
        self._path = path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute("""
              CREATE TABLE IF NOT EXISTS checkpoints (
                project TEXT NOT NULL, repository TEXT NOT NULL, ref TEXT NOT NULL,
                sha TEXT NOT NULL, PRIMARY KEY(project, repository, ref)
              )
            """)
            await db.commit()

    async def get(self, project: str, repository: str, ref: str) -> str | None:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT sha FROM checkpoints WHERE project=? AND repository=? AND ref=?",
                (project, repository, ref),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def list_for_repository(self, project: str, repository: str) -> dict[str, str]:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT ref, sha FROM checkpoints WHERE project=? AND repository=?",
                (project, repository),
            )
            rows = await cur.fetchall()
        return {str(ref): str(sha) for ref, sha in rows}

    async def set(self, project: str, repository: str, ref: str, sha: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO checkpoints VALUES(?,?,?,?) "
                "ON CONFLICT(project,repository,ref) DO UPDATE SET sha=excluded.sha",
                (project, repository, ref, sha),
            )
            await db.commit()

    async def delete(self, project: str, repository: str, ref: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "DELETE FROM checkpoints WHERE project=? AND repository=? AND ref=?",
                (project, repository, ref),
            )
            await db.commit()
