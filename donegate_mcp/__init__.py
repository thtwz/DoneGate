from __future__ import annotations

from pathlib import Path

_pkg_root = Path(__file__).resolve().parent
_src_pkg = _pkg_root.parent / "src" / "donegate_mcp"
__path__ = [str(_src_pkg)]

# Keep source-checkout imports consistent with the installed package.
exec((_src_pkg / "__init__.py").read_text(encoding="utf-8"))
