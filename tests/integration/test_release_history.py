async def test_old_release_remains_queryable_after_new_release(app_harness) -> None:
    await app_harness.services.index_release("v3.8.0", {"PaymentRetry.max_attempts": "3"})
    await app_harness.services.index_release("v4.2.0", {"PaymentRetry.max_attempts": "5"})
    old = await app_harness.search("PaymentRetry max attempts", "payments", "v3.8.0")
    new = await app_harness.search("PaymentRetry max attempts", "payments", "v4.2.0")
    assert any("3" in x["summary"] for x in old)
    assert any("5" in x["summary"] for x in new)
    assert not any("5" in x["summary"] for x in old)
