"""Cross-app public API views."""
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, Count
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.properties.models import Property


class MarketStatsView(APIView):
    """Return cached market-level listing statistics."""

    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = (
            "market_stats:"
            f"city={request.query_params.get('city', '')}:"
            f"transaction_type={request.query_params.get('transaction_type', '')}"
        )
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)

        queryset = Property.objects.filter(status="LISTED")
        city = request.query_params.get("city")
        transaction_type = request.query_params.get("transaction_type")
        if city:
            queryset = queryset.filter(city__slug=city)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        prices = list(queryset.order_by("price").values_list("price", flat=True))
        median_price = self.calculate_median(prices)

        area_rows = queryset.exclude(area=0).values_list("price", "area")
        price_per_sqm_values = [
            price / area for price, area in area_rows if price is not None and area
        ]
        avg_price_per_sqm = (
            sum(price_per_sqm_values) / len(price_per_sqm_values)
            if price_per_sqm_values
            else Decimal("0")
        )

        response = {
            "total_listings": queryset.count(),
            "avg_price_per_sqm": round(avg_price_per_sqm, 2),
            "median_price": median_price,
            "by_city": [
                {
                    "city": row["city__name"],
                    "count": row["count"],
                    "avg_price": row["avg_price"],
                }
                for row in queryset.values("city__name")
                .annotate(count=Count("id"), avg_price=Avg("price"))
                .order_by("-count")
            ],
            "by_type": [
                {
                    "type": row["property_category"],
                    "count": row["count"],
                    "avg_price": row["avg_price"],
                }
                for row in queryset.values("property_category")
                .annotate(count=Count("id"), avg_price=Avg("price"))
                .order_by("-count")
            ],
            "price_ranges": [
                {"range": "0-500k", "count": queryset.filter(price__lt=500000).count()},
                {
                    "range": "500k-1M",
                    "count": queryset.filter(price__gte=500000, price__lt=1000000).count(),
                },
                {
                    "range": "1M-3M",
                    "count": queryset.filter(price__gte=1000000, price__lt=3000000).count(),
                },
                {"range": "3M+", "count": queryset.filter(price__gte=3000000).count()},
            ],
        }
        cache.set(cache_key, response, timeout=60 * 60)
        return Response(response)

    def calculate_median(self, prices):
        """Calculate median price from an ordered price list."""
        if not prices:
            return Decimal("0")
        midpoint = len(prices) // 2
        if len(prices) % 2:
            return prices[midpoint]
        return (prices[midpoint - 1] + prices[midpoint]) / 2
