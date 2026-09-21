"""
Permission catalog for RBAC / FBAC.

Codes are fixed in software; admins grant them via the Access Control UI.
"""

# (module_code, label)
MODULES = (
    ("dashboard", "Dashboard"),
    ("quotes", "Quotes"),
    ("clients", "Clients"),
    ("materials", "Materials"),
    ("machines", "Machines"),
    ("labor", "Labor Roles"),
    ("processes", "Processes"),
    ("subprocesses", "Sub Processes"),
    ("custom_fields", "Custom Fields"),
    ("imports", "Imports"),
    ("error_logs", "Error Logs"),
    ("access_control", "Access Control"),
)

# Standard CRUD-style actions shown in the matrix columns
STANDARD_ACTIONS = (
    ("view", "View"),
    ("create", "Create"),
    ("edit", "Edit"),
    ("soft_delete", "Soft Delete"),
    ("permanent_delete", "Permanent Delete"),
    ("admin", "Admin"),
)

# Extra actions (module, action, label) — Quotes-specific and similar
EXTRA_ACTIONS = (
    ("quotes", "calculate", "Calculate"),
    ("quotes", "issue", "Issue"),
    ("quotes", "clone", "Clone"),
    ("quotes", "preview_pdf", "Preview PDF"),
    ("imports", "upload", "Upload"),
    ("imports", "download_template", "Download template"),
    ("error_logs", "purge", "Purge"),
    ("access_control", "manage_roles", "Manage roles"),
    ("access_control", "assign_users", "Assign users"),
)

# Default matrix columns (extras are managed under Admin / dedicated checks)
MATRIX_ACTIONS = tuple(a[0] for a in STANDARD_ACTIONS)


def all_permission_defs():
    """Yield (module, action, label) for every grantable permission."""
    labels = {m: label for m, label in MODULES}
    for module, _ in MODULES:
        for action, action_label in STANDARD_ACTIONS:
            yield module, action, f"{labels[module]} — {action_label}"
    for module, action, label in EXTRA_ACTIONS:
        yield module, action, f"{labels.get(module, module)} — {label}"
