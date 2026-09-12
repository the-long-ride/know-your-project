async def test_source_text_never_appears_in_mcp_response(app_harness) -> None:
    raw = "private void HighlySensitiveImplementationSecret() {}"
    await app_harness.services.index_source("Secret.cs", raw)
    response = await app_harness.search("sensitive implementation", "payments")
    assert raw not in str(response)
    assert "HighlySensitiveImplementationSecret() {}" not in str(response)
    assert response
