"""scripts/research_app.py's _connections() must have a bounded TTL --
added 2026-11-15 (OPERATIONS.md, BUGS.md Bug #20) after confirming a
long-lived, TTL-less @st.cache_resource connection can hold
warehouse.duckdb open for as long as the Streamlit server process runs
(potentially days), colliding with fibo_evening.py's write connection.
DuckDB's local-file concurrency is N-readers-XOR-1-writer, so even
read_only=True (already in place) does not prevent this collision --
the TTL bounds how long any single connection instance can be held
instead.

DELIBERATELY NEVER IMPORTS research_app.py: that module opens a REAL
connection to the real data/warehouse.duckdb at module level
(`warehouse_con, intraday_con = _connections()`, run unconditionally as
plain Streamlit-script top-level code) and caches it for the lifetime of
the process -- importing it from inside a pytest run would leave that
connection open for the rest of the test SESSION, blocking every later
test that needs a real read-write connection to the same file. (Found
live: an earlier draft of this test imported the module directly and
caused 19 unrelated test errors elsewhere in the same run, the exact
collision class this whole fix exists to prevent -- not a hypothetical.)
Checked by static source inspection instead.
"""
from __future__ import annotations

import ast
from pathlib import Path

SOURCE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "research_app.py"


def _find_decorated_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {SOURCE_PATH}")


def test_connections_cache_resource_has_a_bounded_ttl():
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    fn = _find_decorated_function(tree, "_connections")

    assert fn.decorator_list, "_connections must be decorated with @st.cache_resource"
    decorator = fn.decorator_list[0]
    assert isinstance(decorator, ast.Call), (
        "@st.cache_resource must be CALLED with a ttl= argument, not used bare "
        "(a bare @st.cache_resource has no TTL at all)"
    )
    ttl_kwargs = {kw.arg: kw.value for kw in decorator.keywords}
    assert "ttl" in ttl_kwargs, "_connections's cache_resource call must set ttl="

    # The ttl= value is a name (e.g. _CONNECTION_TTL_SECONDS), not a literal --
    # resolve it from the module's own top-level assignment.
    ttl_name = ttl_kwargs["ttl"].id
    module_source = SOURCE_PATH.read_text(encoding="utf-8")
    namespace: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == ttl_name for t in node.targets
        ):
            exec(compile(ast.Expression(node.value), "<ttl>", "eval"), {}, namespace)
            ttl_value = eval(compile(ast.Expression(node.value), "<ttl>", "eval"))
            assert ttl_value == 15 * 60, f"expected a 15-minute TTL, got {ttl_value}s"
            return
    raise AssertionError(f"could not resolve {ttl_name}'s value from module source")


def test_both_cached_connections_still_use_get_read_connection():
    """Guards against a future edit silently swapping a read-only helper
    for a write-capable one -- read_only=True is not a mitigation for the
    lock-collision class (OPERATIONS.md), but it is still the right mode
    for a tool that should never be able to write to the warehouse."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "get_read_connection as get_warehouse_con" in source
    assert "get_read_connection as get_intraday_con" in source
    assert "get_connection" not in source.replace("get_read_connection", ""), (
        "research_app.py must never import a write-capable get_connection"
    )
