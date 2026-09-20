import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_schema_doc.py"


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("generate_schema_doc", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_documentation_matches_the_models(generator):
    """docs/DB_SCHEMA.md and the README diagram are generated from the models; a model change must regenerate them."""
    if not generator.README_PATH.exists():
        pytest.skip("the repository root is not available (backend copied on its own)")
    stale = generator.stale_files()
    assert stale == [], f"Out of date: {', '.join(stale)}. Run from backend/: python scripts/generate_schema_doc.py"


def test_every_table_is_described(generator):
    from app.database import Base

    assert set(generator.TABLE_NOTES) == {t.name for t in Base.metadata.sorted_tables}


def test_the_diagram_covers_every_relationship(generator):
    from app.database import Base

    text = generator.diagram()
    foreign_keys = [fk for t in Base.metadata.sorted_tables for fk in t.foreign_keys]
    assert text.count("--o{") == len(foreign_keys)
    assert text.startswith("```mermaid\nerDiagram") and text.endswith("```")
