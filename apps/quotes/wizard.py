"""
Quote creation wizard — step registry.

Steps are data-driven so Machine / Labor (etc.) can be inserted later without
rewriting the wizard shell. Enable a step by adding it to QUOTE_WIZARD_STEPS.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WizardStep:
    id: str
    label: str
    # If False, step is skipped in navigation (kept in registry for future use).
    enabled: bool = True
    # If True, a Quote row must already exist before this step can open.
    requires_quote: bool = True


# Order matters. Insert future steps (machines, labor) between processes and preview.
QUOTE_WIZARD_STEPS: tuple[WizardStep, ...] = (
    WizardStep(id="details", label="Quote details", requires_quote=False),
    WizardStep(id="processes", label="Processes", requires_quote=True),
    # Future (disabled until wired):
    WizardStep(id="machines", label="Machines", enabled=False, requires_quote=True),
    WizardStep(id="labor", label="Labor", enabled=False, requires_quote=True),
    WizardStep(id="preview", label="Quote preview", requires_quote=True),
)


def enabled_steps() -> list[WizardStep]:
    return [s for s in QUOTE_WIZARD_STEPS if s.enabled]


def get_step(step_id: str) -> WizardStep | None:
    for s in QUOTE_WIZARD_STEPS:
        if s.id == step_id:
            return s
    return None


def step_index(step_id: str) -> int:
    for i, s in enumerate(enabled_steps()):
        if s.id == step_id:
            return i
    return -1


def adjacent_step(step_id: str, *, direction: int) -> WizardStep | None:
    """direction: -1 previous, +1 next among enabled steps."""
    steps = enabled_steps()
    idx = step_index(step_id)
    if idx < 0:
        return None
    nxt = idx + direction
    if 0 <= nxt < len(steps):
        return steps[nxt]
    return None


def wizard_progress(current_id: str) -> list[dict]:
    """
    Build chevron progress items:
    status = completed | current | upcoming
    """
    steps = enabled_steps()
    cur = step_index(current_id)
    items = []
    for i, s in enumerate(steps):
        if cur < 0:
            status = "upcoming"
        elif i < cur:
            status = "completed"
        elif i == cur:
            status = "current"
        else:
            status = "upcoming"
        items.append({"id": s.id, "label": s.label, "status": status, "index": i + 1})
    return items
