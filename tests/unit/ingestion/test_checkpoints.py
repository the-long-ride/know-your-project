async def test_checkpoint_round_trip(tmp_path) -> None:
    from know_your_project.ingestion.checkpoints import SqliteCheckpointStore

    store = SqliteCheckpointStore(str(tmp_path / "state.db"))
    await store.initialize()
    assert await store.get("p", "r", "main") is None
    await store.set("p", "r", "main", "a" * 40)
    assert await store.get("p", "r", "main") == "a" * 40
