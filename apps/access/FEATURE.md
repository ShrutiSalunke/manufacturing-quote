# Access Control (RBAC + FBAC) — optional feature pack

This app is designed to be merged or cherry-picked as a **complete feature**.

## Enable

1. App is listed in `INSTALLED_APPS` as `apps.access`.
2. Set env `FEATURE_RBAC=True` (default on this feature branch).
3. Run:

```bash
python manage.py migrate access
python manage.py seed_access
```

## Disable (Main / basic clients)

- Set `FEATURE_RBAC=False`, **or** omit this app from the branch entirely.
- Legacy `User.role` (`ADMIN` / `QUOTER`) continues to work.
- Access Control UI is hidden; `has_perm` falls back to legacy rules.

## Safe behavior

- Does **not** remove `User.role`.
- Users with no `UserRole` rows still use legacy role checks (no errors after migrate before seed).
- Superusers always allowed.
- Migrations live only under `apps/access/migrations/` — safe to omit from Main.

## Seed roles

| Level | Code | Intent |
|-------|------|--------|
| 1 | super_admin | All permissions |
| 2 | plant_admin | All except access_control |
| 3 | quoter | Quotes/clients + catalog view |
| 4 | viewer | Read-only |

## App-wide gating (merge-safe)

- Views use `@require_perm(module, action)` from `apps.core.decorators`.
- Templates use `{% load mq_perms %}` + `{% can "module" "action" %}`.
- When `FEATURE_RBAC=False` (or Access app unavailable), checks fall back to legacy ADMIN/QUOTER rules — Main-style deploys keep previous behavior.
- Enabling Access Control does not require rewriting Main; turn on `FEATURE_RBAC`, migrate, and `seed_access`.
