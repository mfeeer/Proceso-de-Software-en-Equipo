import pytest


@pytest.mark.django_db
def test_health_endpoint(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
