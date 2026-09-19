"""Formula evaluation engine using simpleeval (safe math only)."""
import ast
import math
import re
from collections import defaultdict, deque

from simpleeval import SimpleEval, DEFAULT_OPERATORS

IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class FormulaError(Exception):
    pass


SAFE_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
}


def validate_identifier(code: str) -> bool:
    return bool(IDENTIFIER_RE.match(code or ""))


def _safe_names(names: dict) -> dict:
    return {k: float(v) if isinstance(v, (int, float)) else v for k, v in names.items()}


def formula_referenced_names(expression: str) -> set[str]:
    """
    Return identifier names used in an expression (excluding safe function names).
    Raises FormulaError on invalid syntax / disallowed constructs.
    """
    if expression is None or str(expression).strip() == "":
        return set()
    expr = str(expression).strip()
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Invalid expression syntax: {exc}") from exc
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda, ast.ListComp)):
            raise FormulaError("Unsupported construct in formulas")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCTIONS:
                raise FormulaError(
                    f"Function not allowed: {getattr(node.func, 'id', ast.dump(node.func))}"
                )
        if isinstance(node, ast.Name) and node.id not in SAFE_FUNCTIONS:
            names.add(node.id)
    return names


def validate_formula_against_fields(expression: str, allowed_field_codes) -> None:
    """
    Ensure expression only references allowed field codes (+ constants / safe functions).
    Raises FormulaError if unknown names are used (including MAT_*).
    """
    allowed = {(c or "").upper() for c in (allowed_field_codes or []) if c}
    names = formula_referenced_names(expression or "0")

    # Field codes must be written exactly as defined (uppercase A-Z / digits / _)
    wrong_case = sorted(n for n in names if n.upper() in allowed and n != n.upper())
    if wrong_case:
        raise FormulaError(
            "Field codes must be uppercase exactly as defined "
            f"(use {', '.join(n.upper() for n in wrong_case)}, not {', '.join(wrong_case)})."
        )

    unknown = sorted({n.upper() for n in names} - allowed)
    if unknown:
        mat = [n for n in unknown if n.startswith("MAT_")]
        other = [n for n in unknown if not n.startswith("MAT_")]
        parts = []
        if mat:
            parts.append(
                "Material values cannot be used directly in the formula "
                f"({', '.join(mat)}). Add a field and set Auto-fill from material instead."
            )
        if other:
            parts.append(
                "Unknown field code(s): "
                + ", ".join(other)
                + ". Use only fields defined above (and numbers)."
            )
        raise FormulaError(" ".join(parts))


def evaluate_expression(expression: str, names: dict):
    if expression is None or str(expression).strip() == "":
        raise FormulaError("Empty expression")
    expr = str(expression).strip()
    evaluator = SimpleEval(operators=DEFAULT_OPERATORS.copy())
    evaluator.functions = SAFE_FUNCTIONS.copy()
    evaluator.names = _safe_names(names)
    # Disallow attribute access / fancy constructs by parsing
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Invalid expression syntax: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Subscript, ast.Call, ast.Lambda, ast.ListComp)):
            if isinstance(node, ast.Call):
                # allow only whitelisted function names
                if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCTIONS:
                    raise FormulaError(f"Function not allowed: {ast.dump(node)}")
            elif isinstance(node, ast.Attribute):
                raise FormulaError("Attribute access is not allowed in formulas")
            elif isinstance(node, (ast.Subscript, ast.Lambda, ast.ListComp)):
                raise FormulaError("Unsupported construct in formulas")
    try:
        return evaluator.eval(expr)
    except Exception as exc:
        raise FormulaError(f"Evaluation failed ({expr}): {exc}") from exc


def topological_formula_order(formulas: list[tuple[str, str]]) -> list[str]:
    """
    formulas: list of (code, expression)
    Returns codes in evaluation order. Raises FormulaError on cycles.
    """
    codes = {code for code, _ in formulas}
    deps = {code: set() for code, _ in formulas}
    for code, expr in formulas:
        tokens = set(re.findall(r"[A-Z][A-Z0-9_]*", expr or ""))
        deps[code] = {t for t in tokens if t in codes and t != code}

    indegree = {c: 0 for c in codes}
    reverse = defaultdict(set)
    for code, ds in deps.items():
        for d in ds:
            reverse[d].add(code)
            indegree[code] += 1

    queue = deque([c for c, n in indegree.items() if n == 0])
    order = []
    while queue:
        c = queue.popleft()
        order.append(c)
        for nxt in reverse[c]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(codes):
        raise FormulaError("Circular dependency detected among formulas")
    return order
