"""Scaffolding smoke test: every planned module imports (stdlib unittest)."""
from __future__ import annotations

import unittest


class TestScaffolding(unittest.TestCase):
    def test_imports(self) -> None:
        import script2prompt.parsers.base  # noqa: F401
        import script2prompt.parsers.plaintext  # noqa: F401
        import script2prompt.parsers.fountain  # noqa: F401
        import script2prompt.parsers.fdx  # noqa: F401
        import script2prompt.parsers.pdf  # noqa: F401
        import script2prompt.core.config  # noqa: F401
        import script2prompt.core.scenes  # noqa: F401
        import script2prompt.core.characters  # noqa: F401
        import script2prompt.core.chunker  # noqa: F401
        import script2prompt.core.modes  # noqa: F401
        import script2prompt.core.prompts  # noqa: F401
        import script2prompt.core.h3_builder  # noqa: F401
        import script2prompt.core.ref_manifest  # noqa: F401
        import script2prompt.core.llm  # noqa: F401
        import script2prompt.core.fallback  # noqa: F401
        import script2prompt.core.validator  # noqa: F401
        import script2prompt.app.web  # noqa: F401

    def test_config_defaults(self) -> None:
        from script2prompt.core.config import load

        cfg = load(path="nonexistent.toml", local_override="nonexistent-local.toml")
        self.assertEqual(cfg["project"]["mode"], "T2VA")


if __name__ == "__main__":
    unittest.main()
