"""The catalog is all the builders know of the buildings: it must say what the code does."""
from __future__ import annotations

import pytest

from orkcraft.realm import catalog


@pytest.mark.parametrize("type_id", sorted(t.id for t in catalog.TYPES.values() if t.config))
def test_every_setting_is_explained(type_id: str):
    help_ = catalog.CONFIG_HELP.get(type_id, {})
    assert set(help_) == set(catalog.TYPES[type_id].config), f"{type_id}: CONFIG_HELP and config differ"
    assert all(h.strip() for h in help_.values())


def test_the_tables_name_only_real_types():
    for table in (catalog.TAKES, catalog.EFFECTS, catalog.CONFIG_HELP):
        assert set(table) <= set(catalog.TYPES)


def test_the_text_spells_out_settings_only_where_asked():
    signpost, mill = catalog.TYPES["signpost"], catalog.TYPES["mill"]
    full = catalog.catalog_text([signpost, mill])
    some = catalog.catalog_text([signpost, mill], detail={"mill"})
    assert "contains <text>" in full and "grep: <regex>" in full
    assert "contains <text>" not in some and "rules?" in some and "grep: <regex>" in some
    assert "takes from a road: anything" in full and "signpost.routed [text]" in full
