"""Shared API URL routes."""
from django.urls import path

from common.views import MarketStatsView


urlpatterns = [
    path("stats/market/", MarketStatsView.as_view(), name="market-stats"),
]
