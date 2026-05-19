"""Serializers for scraper monitoring APIs."""
from rest_framework import serializers

from apps.scraper.models import ScrapeError, ScrapeJob


class ReadOnlyModelSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields


class ScrapeJobSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = ScrapeJob
        fields = "__all__"


class ScrapeErrorSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = ScrapeError
        fields = "__all__"
