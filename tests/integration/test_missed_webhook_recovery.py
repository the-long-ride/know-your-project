async def test_reconciliation_processes_changed_remote_ref(app_harness) -> None:
    await app_harness.services.set_checkpoint("repo", "refs/heads/main", "a" * 40)
    app_harness.services.set_remote_ref("repo", "refs/heads/main", "b" * 40)
    await app_harness.services.reconcile()
    assert await app_harness.services.get_checkpoint("repo", "refs/heads/main") == "b" * 40
