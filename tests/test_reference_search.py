import pytest

from forge_backend import storage
from forge_backend.storage import refresh_reference_type, search_reference_records

FIXTURES = [
    ("race", "srd-2024_elf", "Elf", "srd-2024"),
    ("class", "srd-2024_wizard", "Wizard", "srd-2024"),
    ("background", "srd-2024_sage", "Sage", "srd-2024"),
    ("equipment", "srd-2024_longsword", "Longsword", "srd-2024"),
    ("spell", "srd-2024_magic-missile", "Magic Missile", "srd-2024"),
    ("skill", "acrobatics", "Acrobatics", "core"),
    ("monster", "srd-2024_aboleth", "Aboleth", "srd-2024"),
    ("magic_item", "srd-2024_magic-lens", "Magic Lens", "srd-2024"),
    ("condition", "blinded", "Blinded", "core"),
]


def _envelope(ref_type, key, name, document, **data):
    return {
        "type": ref_type,
        "key": key,
        "name": name,
        "document": document,
        "data": {"key": key, "name": name, **data},
    }


@pytest.fixture
def populated(redis_conn):
    for ref_type, key, name, document in FIXTURES:
        extra = {}
        if ref_type == "equipment":
            # Magic appears only in non-name fields; it must not match Longsword.
            extra = {"description": "A Magic blade", "key_hint": "magic"}
        refresh_reference_type(
            redis_conn, ref_type, [_envelope(ref_type, key, name, document, **extra)]
        )
    return redis_conn


def _public(api_client, path, params=None):
    # Clear the auth override: these routes must be public.
    api_client.app.dependency_overrides.clear()
    return api_client.get(path, params=params)


def _triples(body):
    return [(r["name"], r["type"], r["key"]) for r in body]


@pytest.mark.integration
@pytest.mark.test_id("ST-27")
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Elf", [("Elf", "race", "srd-2024_elf")]),
        ("Wizard", [("Wizard", "class", "srd-2024_wizard")]),
        ("Sage", [("Sage", "background", "srd-2024_sage")]),
        ("Longsword", [("Longsword", "equipment", "srd-2024_longsword")]),
        ("Magic Missile", [("Magic Missile", "spell", "srd-2024_magic-missile")]),
        ("Aboleth", [("Aboleth", "monster", "srd-2024_aboleth")]),
        ("Magic Lens", [("Magic Lens", "magic_item", "srd-2024_magic-lens")]),
        ("Blinded", [("Blinded", "condition", "blinded")]),
        ("Acrobatics", [("Acrobatics", "skill", "acrobatics")]),
    ],
)
def test_full_name_search_returns_exact_envelope(api_client, populated, query, expected):
    response = _public(api_client, "/search", {"q": query})
    assert response.status_code == 200
    assert _triples(response.json()) == expected
    body = response.json()[0]
    assert body["data"]["key"] == expected[0][2]
    assert set(body) == {"type", "key", "name", "document", "data"}


@pytest.mark.integration
@pytest.mark.test_id("ST-28")
def test_no_match_returns_empty_array(api_client, populated):
    response = _public(api_client, "/search", {"q": "zzzz-no-such-reference-us24"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
@pytest.mark.test_id("ST-28")
def test_valid_term_on_empty_database_returns_empty_array(api_client, redis_conn):
    response = _public(api_client, "/search", {"q": "Magic"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
@pytest.mark.test_id("ST-29")
def test_partial_name_matches_only_names_sorted(api_client, populated):
    refresh_reference_type(
        populated,
        "spell",
        [
            _envelope("spell", "srd-2024_magic-missile", "Magic Missile", "srd-2024"),
            _envelope("spell", "srd-2024_magic-lens", "Magic Lens", "srd-2024"),
        ],
    )
    refresh_reference_type(
        populated,
        "magic_item",
        [_envelope("magic_item", "srd-2024_magic-lens", "Magic Lens", "srd-2024")],
    )
    expected = [
        ("Magic Lens", "magic_item", "srd-2024_magic-lens"),
        ("Magic Lens", "spell", "srd-2024_magic-lens"),
        ("Magic Missile", "spell", "srd-2024_magic-missile"),
    ]
    plain = _public(api_client, "/search", {"q": "Magic"})
    padded = _public(api_client, "/search", {"q": "  mAgIc  "})
    assert plain.status_code == padded.status_code == 200
    assert _triples(plain.json()) == expected
    assert _triples(padded.json()) == expected
    assert "Longsword" not in [r["name"] for r in plain.json()]


@pytest.mark.integration
@pytest.mark.parametrize("query", ["", "   ", None])
def test_blank_or_missing_query_is_422(api_client, populated, query):
    params = {} if query is None else {"q": query}
    assert _public(api_client, "/search", params).status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize("query", ["*", "["])
def test_glob_and_regex_characters_are_literal(api_client, populated, query):
    response = _public(api_client, "/search", {"q": query})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
def test_equal_names_keep_separate_identities_with_tiebreak(api_client, populated):
    refresh_reference_type(
        populated,
        "spell",
        [_envelope("spell", "srd-2024_magic-lens", "Magic Lens", "srd-2024")],
    )
    refresh_reference_type(
        populated,
        "magic_item",
        [_envelope("magic_item", "srd-2024_magic-lens", "Magic Lens", "srd-2024")],
    )
    response = _public(api_client, "/search", {"q": "Magic Lens"})
    assert _triples(response.json()) == [
        ("Magic Lens", "magic_item", "srd-2024_magic-lens"),
        ("Magic Lens", "spell", "srd-2024_magic-lens"),
    ]


def test_dal_matches_casefolded_name_not_simple_lowercase(monkeypatch):
    record = _envelope("equipment", "srd-2024_strasse", "Straße", "srd-2024")
    monkeypatch.setattr(
        storage,
        "list_reference_records",
        lambda _conn, ref_type: [record] if ref_type == "equipment" else [],
    )
    assert search_reference_records(None, "STRASSE") == [record]


def test_dal_empty_normalized_query_returns_empty_without_reading(monkeypatch):
    def boom(_conn, _ref_type):
        raise AssertionError("must not read the datastore for a blank query")

    monkeypatch.setattr(storage, "list_reference_records", boom)
    assert search_reference_records(None, "   ") == []


@pytest.mark.integration
def test_search_second_page_returns_remaining_sorted_results(api_client, redis_conn):
    records = [
        _envelope("spell", f"paged-{i:03d}", f"Paged {i:03d}", "srd-2024") for i in range(101)
    ]
    refresh_reference_type(redis_conn, "spell", records)
    first = _public(api_client, "/search", {"q": "Paged"})
    second = _public(api_client, "/search", {"q": "Paged", "page": 2})
    assert first.status_code == second.status_code == 200
    assert len(first.json()) == 100
    assert _triples(second.json()) == [("Paged 100", "spell", "paged-100")]


@pytest.mark.integration
@pytest.mark.parametrize("page", ["0", "-1", "abc"])
def test_search_invalid_page_is_422(api_client, populated, page):
    assert _public(api_client, "/search", {"q": "Magic", "page": page}).status_code == 422


def test_dal_search_pages_are_disjoint_and_cover_all_matches(monkeypatch):
    records = [_envelope("spell", f"k-{i:03d}", f"Bulk {i:03d}", "srd-2024") for i in range(205)]
    monkeypatch.setattr(
        storage,
        "list_reference_records",
        lambda _conn, ref_type: list(records) if ref_type == "spell" else [],
    )
    first = search_reference_records(None, "bulk", page=1)
    second = search_reference_records(None, "bulk", page=2)
    third = search_reference_records(None, "bulk", page=3)
    assert [r["key"] for r in first] == [f"k-{i:03d}" for i in range(100)]
    assert [r["key"] for r in second] == [f"k-{i:03d}" for i in range(100, 200)]
    assert [r["key"] for r in third] == [f"k-{i:03d}" for i in range(200, 205)]
    assert search_reference_records(None, "bulk", page=4) == []


def test_dal_search_invalid_page_raises():
    with pytest.raises(ValueError, match="invalid page"):
        search_reference_records(None, "bulk", page=0)


@pytest.mark.integration
def test_filter_has_results_after_filter(api_client, populated):
    expected = [
        ("Magic Lens", "magic_item", "srd-2024_magic-lens"),
    ]
    response = _public(api_client, "/search", {"q": "Magic", "content_filter": "magic_item"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert _triples(response.json()) == expected


@pytest.mark.integration
def test_filter_has_no_results_after_filter(api_client, populated):
    response = _public(api_client, "/search", {"q": "Magic", "content_filter": "race"})
    assert response.status_code == 200
    assert len(response.json()) == 0
    assert response.json() == []


@pytest.mark.integration
def test_filter_invalid_filter(api_client, populated):
    error_filtering = None
    response = _public(api_client, "/search", {"q": "Magic", "content_filter": "fakeFilter"})
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.parametrize("page", ["0", "-1", "abc"])
def test_filter_invalid_page(api_client, populated, page):
    assert _public(api_client, "/search", {"q": "Magic", "page": page, "content_filter": "magic_item"}).status_code == 422