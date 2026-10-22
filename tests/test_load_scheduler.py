"""Guard the threading contract of the HA-coupled load scheduler.

``load_scheduler`` imports Home Assistant, so it cannot be imported here (the
suite deliberately runs without HA installed, see conftest). The invariant worth
pinning is therefore checked on the source tree with ``ast``.

Home Assistant classifies a ``HassJob`` from the shape of its target: a plain
sync function becomes ``HassJobType.Executor`` and runs in a worker thread,
while a coroutine function or a ``@callback`` runs in the event loop. The hour
boundary tick ends in ``async_dispatcher_send``, which calls
``hass.verify_event_loop_thread`` and raises for a custom integration when it is
off-loop. An undecorated tick therefore dies every hour before the entities are
told about the freshly computed plan: the run-now sensor keeps its stale state
and the automation watching it never fires.
"""

import ast
from pathlib import Path

_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "dynamiczne_info"
    / "load_scheduler.py"
)

_Func = ast.FunctionDef | ast.AsyncFunctionDef


def _tree() -> ast.Module:
    return ast.parse(_SOURCE.read_text(encoding="utf-8"))


def _method(name: str) -> _Func:
    for node in ast.walk(_tree()):
        if isinstance(node, _Func) and node.name == name:
            return node
    raise AssertionError(f"method {name} not found in {_SOURCE.name}")


def _runs_in_event_loop(func: _Func) -> bool:
    """Mirror HassJob's rule: coroutine functions and callbacks stay on-loop."""
    if isinstance(func, ast.AsyncFunctionDef):
        return True
    return any(
        (getattr(node, "id", None) or getattr(node, "attr", None)) == "callback"
        for node in func.decorator_list
    )


def _tracked_methods() -> set[str]:
    """Names of the methods handed to any ``async_track_*`` helper."""
    defined = {node.name for node in ast.walk(_tree()) if isinstance(node, _Func)}
    names: set[str] = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        called = getattr(node.func, "id", None) or getattr(node.func, "attr", "")
        if not called.startswith("async_track_"):
            continue
        names.update(
            arg.attr
            for arg in node.args
            if isinstance(arg, ast.Attribute) and arg.attr in defined
        )
    return names


def test_hour_tick_runs_in_the_event_loop():
    assert _runs_in_event_loop(_method("_tick"))


def test_every_tracked_job_runs_in_the_event_loop():
    tracked = _tracked_methods()
    assert tracked, "expected at least one async_track_* registration"
    off_loop = [name for name in tracked if not _runs_in_event_loop(_method(name))]
    assert not off_loop, f"tracked off-loop: {sorted(off_loop)}"
