import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_register_login_and_access_protected_agency_endpoint(api_client):
    register_response = api_client.post(
        reverse("agencies:auth-register"),
        {
            "email": "new-owner@example.com",
            "password": "strong-password",
            "first_name": "New",
            "last_name": "Owner",
            "agency_name": "New Agency",
            "phone": "212600000002",
        },
        format="json",
    )

    assert register_response.status_code == 201
    assert "access" in register_response.data
    assert "refresh" in register_response.data

    login_response = api_client.post(
        reverse("agencies:auth-login"),
        {"email": "new-owner@example.com", "password": "strong-password"},
        format="json",
    )
    assert login_response.status_code == 200
    access = login_response.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    me_response = api_client.get(reverse("agency-me"))

    assert me_response.status_code == 200
    assert me_response.data["name"] == "New Agency"


@pytest.mark.django_db
def test_authenticated_agency_user_fixture_accesses_me(authenticated_agency_user):
    response = authenticated_agency_user["client"].get(reverse("agency-me"))

    assert response.status_code == 200
    assert response.data["name"] == "Yakeey Test Agency"
