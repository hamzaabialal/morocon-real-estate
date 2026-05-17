import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_property_list_endpoint_filters_by_city(api_client, sample_property, city):
    response = api_client.get(reverse("property-list"), {"city": city.slug})

    assert response.status_code == 200
    assert response.data["count"] == 1
    result = response.data["results"][0]
    assert result["yakeey_ref"] == sample_property.yakeey_ref
    assert result["city"] == "Casablanca"
    assert result["district"] == "Maarif"
    assert result["neighborhood"] == "Gauthier"
