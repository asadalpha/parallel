from app.main import app


def test_openapi_lists_public_write_admin_and_ai_routes() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/locations" in paths
    assert "/api/v1/stories/{story_id}" in paths
    assert "/api/v1/stories/{story_id}/submit" in paths
    assert "/api/v1/admin/moderation" in paths
    assert "/api/v1/concierge/recommend" in paths
    assert "/api/v1/ai/story-assist" in paths
    assert "/api/v1/media/upload" in paths
