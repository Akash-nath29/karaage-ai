import uuid

from fastapi.testclient import TestClient

MISSING = str(uuid.uuid4())


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_workspace_crud(client: TestClient) -> None:
    created = client.post("/api/v1/workspaces", json={"name": "  Semester 5 ", "description": "CSE"})
    assert created.status_code == 201
    ws = created.json()
    assert ws["name"] == "Semester 5"  # whitespace stripped

    assert [w["id"] for w in client.get("/api/v1/workspaces").json()] == [ws["id"]]

    patched = client.patch(f"/api/v1/workspaces/{ws['id']}", json={"name": "Sem 5", "description": None})
    assert patched.json()["name"] == "Sem 5"
    assert patched.json()["description"] == "CSE"  # explicit null leaves field untouched

    assert client.delete(f"/api/v1/workspaces/{ws['id']}").status_code == 204
    assert client.get(f"/api/v1/workspaces/{ws['id']}").status_code == 404


def test_workspace_validation_and_404(client: TestClient) -> None:
    assert client.post("/api/v1/workspaces", json={"name": "   "}).status_code == 422
    assert client.patch(f"/api/v1/workspaces/{MISSING}", json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/v1/workspaces/{MISSING}").status_code == 404
    assert client.get("/api/v1/workspaces/not-a-uuid").status_code == 422


def test_course_crud(client: TestClient) -> None:
    ws = client.post("/api/v1/workspaces", json={"name": "WS"}).json()
    base = f"/api/v1/workspaces/{ws['id']}/courses"

    created = client.post(base, json={"title": "DBMS", "code": "CS501", "term": "Sem 5"})
    assert created.status_code == 201
    course = created.json()
    assert course["workspace_id"] == ws["id"]

    assert [c["id"] for c in client.get(base).json()] == [course["id"]]

    patched = client.patch(f"/api/v1/courses/{course['id']}", json={"title": "Database Systems"})
    assert patched.json()["title"] == "Database Systems"
    assert patched.json()["code"] == "CS501"

    assert client.delete(f"/api/v1/courses/{course['id']}").status_code == 204
    assert client.get(f"/api/v1/courses/{course['id']}").status_code == 404


def test_course_requires_existing_workspace(client: TestClient) -> None:
    missing = f"/api/v1/workspaces/{MISSING}/courses"
    assert client.post(missing, json={"title": "X"}).status_code == 404
    assert client.get(missing).status_code == 404


def test_courses_scoped_to_workspace_and_cascade(client: TestClient) -> None:
    a = client.post("/api/v1/workspaces", json={"name": "A"}).json()
    b = client.post("/api/v1/workspaces", json={"name": "B"}).json()
    course = client.post(f"/api/v1/workspaces/{a['id']}/courses", json={"title": "Only in A"}).json()

    assert client.get(f"/api/v1/workspaces/{b['id']}/courses").json() == []

    client.delete(f"/api/v1/workspaces/{a['id']}")
    assert client.get(f"/api/v1/courses/{course['id']}").status_code == 404
