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

    async def set(self, project: str, repository: str, ref: str, sha: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO checkpoints VALUES(?,?,?,?) "
                "ON CONFLICT(project,repository,ref) DO UPDATE SET sha=excluded.sha",
                (project, repository, ref, sha),
            )
            await db.commit()
