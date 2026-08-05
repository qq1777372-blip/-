from __future__ import annotations

import unittest

from app.models.entities import AdminUser
from main import normalize_admin_permissions, resolve_admin_permissions


class AdminPermissionTests(unittest.TestCase):
    def test_legacy_editor_keeps_write_access(self) -> None:
        user = AdminUser(role="editor", permissions_json=None)

        permissions = resolve_admin_permissions(user)

        self.assertTrue(permissions)
        self.assertTrue(all(level == "write" for level in permissions.values()))

    def test_custom_permissions_override_role_defaults(self) -> None:
        user = AdminUser(
            role="editor",
            permissions_json=normalize_admin_permissions(
                "editor",
                {"links": "read", "peer_shops": "none"},
            ),
        )

        permissions = resolve_admin_permissions(user)

        self.assertEqual(permissions["links"], "read")
        self.assertEqual(permissions["peer_shops"], "none")
        self.assertEqual(permissions["shop_records"], "write")

    def test_dashboard_always_retains_read_access(self) -> None:
        user = AdminUser(
            role="viewer",
            permissions_json=normalize_admin_permissions("viewer", {"dashboard": "none"}),
        )

        self.assertEqual(resolve_admin_permissions(user)["dashboard"], "read")

    def test_superadmin_permissions_cannot_be_restricted(self) -> None:
        user = AdminUser(role="superadmin", permissions_json='{"links": "none"}')

        self.assertTrue(all(level == "write" for level in resolve_admin_permissions(user).values()))


if __name__ == "__main__":
    unittest.main()
