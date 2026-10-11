from fastapi.testclient import TestClient

from forge_backend.main import app

client = TestClient(app)


def test_create_documents_201_not_200():
    responses = client.get("/openapi.json").json()["paths"]["/characters"]["post"]["responses"]
    assert "201" in responses
    assert "200" not in responses


def test_character_record_uses_wire_key_class():
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    record = schemas["CharacterRecord"]
    assert "class" in record["properties"]
    assert "character_class" not in record["properties"]
    record_list = client.get("/openapi.json").json()["paths"]["/characters"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert record_list["type"] == "array"
    assert record_list["items"]["$ref"].endswith("CharacterRecord")


def test_reference_responses_have_object_schemas():
    schema = client.get("/openapi.json").json()
    record = schema["components"]["schemas"]["ReferenceRecord"]
    assert record["type"] == "object"
    assert {"type", "key", "name", "document", "data"} <= set(record["properties"])
    get_classes = schema["paths"]["/classes"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert get_classes["type"] == "array"


def test_every_character_operation_requires_nonempty_header():
    schema = client.get("/openapi.json").json()
    paths = [
        ("/characters", "post"),
        ("/characters", "get"),
        ("/characters/ids", "get"),
        ("/characters/count", "get"),
        ("/characters/{character_id}", "get"),
        ("/characters/{character_id}/class", "put"),
        ("/characters/{character_id}/equipment", "put"),
    ]
    for path, method in paths:
        params = schema["paths"][path][method].get("parameters", [])
        header = next(p for p in params if p["in"] == "header" and p["name"] == "X-User-Id")
        assert header["required"] is True
        assert header["schema"].get("minLength", 0) >= 1


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
    put_responses = schema["paths"]["/characters/{character_id}/class"]["put"]["responses"]
    assert "400" in put_responses and "404" in put_responses


def test_equipment_contract_exposes_array_and_errors():
    schema = client.get("/openapi.json").json()
    schemas = schema["components"]["schemas"]
    assert schemas["EquipmentSelection"]["properties"]["equipment"]["type"] == "array"
    assert schemas["EquipmentSelection"]["properties"]["equipment"]["items"]["type"] == "string"
    assert "equipment" in schemas["EquipmentSelection"]["required"]
    assert schemas["CharacterRecord"]["properties"]["equipment"]["type"] == "array"
    put = schema["paths"]["/characters/{character_id}/equipment"]["put"]
    assert "400" in put["responses"] and "404" in put["responses"]
