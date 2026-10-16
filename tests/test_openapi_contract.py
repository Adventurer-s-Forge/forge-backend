import pytest
from fastapi.testclient import TestClient

from forge_backend.main import app

client = TestClient(app)


def test_create_documents_201_not_200():
    responses = client.get("/openapi.json").json()["paths"]["/characters"]["post"]["responses"]
    assert "201" in responses
    assert "200" not in responses


def test_character_record_uses_canonical_fields():
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    record = schemas["CharacterRecord"]
    for field in (
        "id",
        "name",
        "level",
        "raceId",
        "sizeChoice",
        "classId",
        "backgroundId",
        "equipmentChoice",
        "purchasedItemIds",
        "abilities",
        "proficientSkillIds",
        "expertiseIds",
        "spellIds",
        "completedSteps",
    ):
        assert field in record["properties"]
    assert "owner" not in record["properties"]
    assert "character_class" not in record["properties"]
    assert record.get("additionalProperties") is False
    record_list = client.get("/openapi.json").json()["paths"]["/characters"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert record_list["type"] == "array"
    assert record_list["items"]["$ref"].endswith("CharacterDocument")
    assert "createdAt" not in schemas["CharacterRecord"]["properties"]
    assert "createdAt" in schemas["CharacterDocument"]["properties"]


def test_reference_responses_have_object_schemas():
    schema = client.get("/openapi.json").json()
    record = schema["components"]["schemas"]["ReferenceRecord"]
    assert record["type"] == "object"
    assert {"type", "key", "name", "document", "data"} <= set(record["properties"])
    get_classes = schema["paths"]["/classes"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert get_classes["type"] == "array"


def test_declared_errors_expose_string_detail():
    schema = client.get("/openapi.json").json()
    assert (
        schema["components"]["schemas"]["ErrorResponse"]["properties"]["detail"]["type"] == "string"
    )
    post_409 = schema["paths"]["/characters"]["post"]["responses"]["409"]
    assert (
        post_409["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ErrorResponse"
    )
    detail_404 = schema["paths"]["/characters/{character_id}"]["get"]["responses"]["404"]
    assert (
        detail_404["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ErrorResponse"
    )


def test_save_operation_exposed():
    schema = client.get("/openapi.json").json()
    put = schema["paths"]["/characters/{character_id}"]["put"]
    assert put["operationId"] == "save_character"
    assert "400" in put["responses"] and "404" in put["responses"]
    ref = put["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("CharacterRecord")


def test_equipment_path_is_singular():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/equipment" in paths
    assert paths["/equipment"]["get"]["operationId"] == "list_items"
    assert "/items" not in paths
    assert "/equipments" not in paths


@pytest.mark.parametrize("path", [
    "/characters/{character_id}/class",
    "/characters/{character_id}/spells",
    "/characters/{character_id}/equipment",
])
def test_retired_subroutes_absent_from_contract(path):
    from forge_backend.main import app
    assert path not in app.openapi()["paths"]