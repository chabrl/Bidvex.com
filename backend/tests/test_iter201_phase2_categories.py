"""
iter201 — Phase 2 tests: vehicle categories + listing form constraints.

Run: cd /app/backend && pytest tests/test_iter201_phase2_categories.py -v
"""
import pytest

from services.vehicle_categories import (
    VEHICLE_CATEGORIES,
    get_category,
    get_subcategory,
    category_requires_dealer_license,
)


def test_15_categories_present():
    """CEO spec: 15 vehicle categories."""
    assert len(VEHICLE_CATEGORIES) == 15


def test_each_category_has_required_fields():
    """Schema integrity — every category must have id/icon/label_en/label_fr/subcategories."""
    for c in VEHICLE_CATEGORIES:
        assert c["id"], c
        assert c["icon"], c
        assert c["label_en"], c
        assert c["label_fr"], c
        assert isinstance(c.get("subcategories"), list)
        for s in c["subcategories"]:
            assert s["id"]
            assert s["label_en"]
            assert s["label_fr"]


def test_only_parts_accessories_open_to_individuals():
    """CEO constraint #3 — parts_accessories is the ONLY category open to non-dealers."""
    open_cats = [c["id"] for c in VEHICLE_CATEGORIES if not c.get("requires_dealer_license", True)]
    assert open_cats == ["parts_accessories"], f"unexpected open categories: {open_cats}"

    assert category_requires_dealer_license("parts_accessories") is False
    assert category_requires_dealer_license("cars_sedans") is True
    assert category_requires_dealer_license("luxury_exotic") is True
    # Unknown category id falls back to True (safe default)
    assert category_requires_dealer_license("does_not_exist") is True


def test_get_category_helpers():
    cat = get_category("trucks_pickups")
    assert cat is not None
    assert cat["icon"] == "🛻"
    assert get_category("nope") is None

    sub = get_subcategory("trucks_pickups", "half_ton")
    assert sub is not None
    assert sub["label_fr"] == "Camionnette demi-tonne"
    assert get_subcategory("trucks_pickups", "nope") is None
    assert get_subcategory("nope", "half_ton") is None


def test_unique_category_and_subcategory_ids():
    """No duplicate category ids; subcategory ids are unique within a category."""
    cat_ids = [c["id"] for c in VEHICLE_CATEGORIES]
    assert len(cat_ids) == len(set(cat_ids))
    for c in VEHICLE_CATEGORIES:
        sub_ids = [s["id"] for s in c["subcategories"]]
        assert len(sub_ids) == len(set(sub_ids)), f"duplicate subcategory in {c['id']}: {sub_ids}"


def test_listing_create_model_accepts_new_fields():
    """VehicleListingCreate must accept category_id, subcategory_id, title_fr, description_fr."""
    from models.vehicle_models import VehicleListingCreate
    fields = VehicleListingCreate.model_fields
    for f in ("category_id", "subcategory_id", "title_fr", "description_fr"):
        assert f in fields, f"VehicleListingCreate is missing {f}"
        assert fields[f].default is None
