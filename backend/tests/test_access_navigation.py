from app.core.roles import Role, accessible_modules


def test_access_settings_navigation_matches_user_management_permission():
    assert "users" in accessible_modules(Role.OWNER)
    for role in Role:
        if role != Role.OWNER:
            assert "users" not in accessible_modules(role)
