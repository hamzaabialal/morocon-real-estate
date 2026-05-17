import pytest
from django.urls import reverse

from apps.analytics.models import PropertyView


@pytest.mark.django_db
def test_track_view_increments_views_count(api_client, sample_property):
    response = api_client.post(
        reverse("property-track-view", kwargs={"pk": sample_property.pk}),
        HTTP_USER_AGENT="pytest",
        REMOTE_ADDR="127.0.0.1",
    )

    assert response.status_code == 200
    sample_property.refresh_from_db()
    assert sample_property.views_count == 1
    assert PropertyView.objects.filter(property=sample_property).count() == 1
