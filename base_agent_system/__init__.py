"""Workspace import shim for the src-layout package during bootstrap."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "base_agent_system"
_SPEC = spec_from_file_location(
    __name__,
    _SRC_PACKAGE / "__init__.py",
    submodule_search_locations=[str(_SRC_PACKAGE)],
)

if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load package from {_SRC_PACKAGE}")

_MODULE = module_from_spec(_SPEC)
sys.modules[__name__] = _MODULE
_SPEC.loader.exec_module(_MODULE)
