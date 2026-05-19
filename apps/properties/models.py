"""Property listing models imported from Yakeey and future data sources."""
import uuid

from django.db import models


class Property(models.Model):
    """Core real estate listing displayed by the Yakeey API."""

    TRANSACTION_TYPE_CHOICES = [("SALE", "Sale"), ("RENT", "Rent")]
    CATEGORY_CHOICES = [
        ("FLAT", "Flat"),
        ("TERRAIN", "Terrain"),
        ("COMMERCIAL_BUILDING", "Commercial Building"),
        ("HOUSE", "House"),
        ("VILLA", "Villa"),
        ("OFFICE", "Office"),
        ("RIAD", "Riad"),
    ]
    TYPE_CHOICES = [
        ("APARTMENT", "Apartment"),
        ("STUDIO", "Studio"),
        ("DUPLEX", "Duplex"),
        ("TRIPLEX", "Triplex"),
        ("RIAD", "Riad"),
        ("OFFICE", "Office"),
        ("TWINNED_HOUSE", "Twinned House"),
        ("STRIPED_HOUSE", "Striped House"),
        ("ISOLATED_HOUSE", "Isolated House"),
    ]
    STATUS_CHOICES = [
        ("LISTED", "Listed"),
        ("SOLD", "Sold"),
        ("RENTED", "Rented"),
        ("ARCHIVED", "Archived"),
    ]
    GENERAL_STATE_CHOICES = [
        ("FAIR", "Fair"),
        ("NEW", "New"),
        ("TO_BE_RENOVATED", "To Be Renovated"),
        ("GOOD", "Good"),
        ("RECENTLY_RENOVATED", "Recently Renovated"),
        ("SEMI_FINISHED", "Semi Finished"),
    ]
    OCCUPATION_STATE_CHOICES = [("EMPTY", "Empty"), ("OCCUPIED", "Occupied")]
    SOURCE_CHOICES = [
        ("yakeey", "Yakeey"),
        ("propertyfinder", "PropertyFinder"),
        ("manual", "Manual"),
    ]
    MEDIA_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("generating", "Generating"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]
    ENRICHMENT_CONFIDENCE_CHOICES = [
        ("HIGH", "HIGH"),
        ("MEDIUM", "MEDIUM"),
        ("NONE", "NONE"),
    ]
    SCRAPE_STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("SCRAPED", "SCRAPED"),
        ("ENRICHED", "ENRICHED"),
        ("FAILED", "FAILED"),
    ]
    LISTING_TYPE_CHOICES = [("SALE", "SALE"), ("RENT", "RENT")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sarouty_id = models.IntegerField(unique=True, null=True, blank=True)
    yakeey_id = models.CharField(max_length=20, null=True, blank=True)
    enrichment_confidence = models.CharField(
        max_length=10, choices=ENRICHMENT_CONFIDENCE_CHOICES, default="NONE"
    )
    scrape_status = models.CharField(
        max_length=20, choices=SCRAPE_STATUS_CHOICES, default="PENDING"
    )
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    listing_type = models.CharField(
        max_length=10, choices=LISTING_TYPE_CHOICES, null=True, blank=True
    )
    yakeey_ref = models.CharField(max_length=30, unique=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    property_category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, blank=True
    )
    property_type = models.CharField(max_length=30, choices=TYPE_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="LISTED")
    price = models.DecimalField(max_digits=19, decimal_places=2)
    currency = models.CharField(max_length=5, default="DH")
    area = models.DecimalField(max_digits=19, decimal_places=2)
    built_area = models.DecimalField(
        max_digits=19, decimal_places=2, null=True, blank=True
    )
    bedrooms = models.IntegerField(default=0)
    bathrooms = models.IntegerField(default=0)
    toilets = models.IntegerField(default=0)
    floor = models.IntegerField(null=True, blank=True)
    total_floors = models.IntegerField(null=True, blank=True)
    construction_year = models.IntegerField(null=True, blank=True)
    condominium_fees = models.IntegerField(null=True, blank=True)
    furnished = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    closed_residence = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    general_state = models.CharField(
        max_length=30, choices=GENERAL_STATE_CHOICES, blank=True
    )
    view = models.CharField(max_length=120, blank=True)
    occupation_state = models.CharField(
        max_length=20, choices=OCCUPATION_STATE_CHOICES, blank=True
    )
    description = models.TextField(blank=True)
    cover_image_url = models.URLField(blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    formatted_address = models.CharField(max_length=255, blank=True)
    main_address = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(blank=True)
    marketplace_url = models.URLField(blank=True)
    agent_name = models.CharField(max_length=150, blank=True)
    agent_phone = models.CharField(max_length=30, blank=True)
    registration_fees = models.DecimalField(
        max_digits=19, decimal_places=2, null=True, blank=True
    )
    total_acquisition_cost = models.DecimalField(
        max_digits=19, decimal_places=2, null=True, blank=True
    )
    land_registration_fees = models.DecimalField(
        max_digits=19, decimal_places=2, null=True, blank=True
    )
    notary_fees = models.DecimalField(
        max_digits=19, decimal_places=2, null=True, blank=True
    )
    views_count = models.IntegerField(default=0)
    city = models.ForeignKey(
        "locations.City", on_delete=models.PROTECT, related_name="properties"
    )
    district = models.ForeignKey(
        "locations.District",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="properties",
    )
    neighborhood = models.ForeignKey(
        "locations.Neighborhood",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="properties",
    )
    agency = models.ForeignKey(
        "agencies.Agency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="properties",
    )
    agency_match_confidence = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="yakeey")
    property_tag = models.CharField(max_length=50, blank=True)
    reel_url = models.URLField(null=True, blank=True)
    square_video_url = models.URLField(null=True, blank=True)
    caption_fr = models.TextField(null=True, blank=True)
    caption_ar = models.TextField(null=True, blank=True)
    caption_hashtags = models.JSONField(default=list, blank=True)
    media_generated_at = models.DateTimeField(null=True, blank=True)
    media_status = models.CharField(
        max_length=20, choices=MEDIA_STATUS_CHOICES, default="pending"
    )
    listed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    short_code = models.CharField(
        max_length=12,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Public short URL slug — auto-derived from the property's UUID.",
    )

    class Meta:
        ordering = ["-listed_at", "-updated_at"]
        verbose_name = "Property"
        verbose_name_plural = "Properties"
        indexes = [
            models.Index(fields=["transaction_type", "status"]),
            models.Index(fields=["property_category", "property_type"]),
            models.Index(fields=["price"]),
            models.Index(fields=["area"]),
        ]

    def __str__(self) -> str:
        return self.yakeey_ref

    def save(self, *args, **kwargs):
        if not self.short_code:
            self.short_code = _make_short_code(self.id)
        super().save(*args, **kwargs)


def _make_short_code(uuid_value):
    """Derive a 6-char base32 code from a UUID (no padding, no ambiguous chars)."""
    import base64
    raw = base64.b32encode(uuid_value.bytes[:5]).decode("ascii").rstrip("=").lower()
    return raw[:6]


class PropertyImage(models.Model):
    """Image belonging to a property listing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="images"
    )
    url = models.URLField()
    order = models.IntegerField(default=0)
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Property Image"
        verbose_name_plural = "Property Images"

    def __str__(self) -> str:
        return f"{self.property_id} image {self.order}"


class PropertyFeatures(models.Model):
    """Amenities and feature measurements associated with one property."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name="features"
    )
    furniture = models.BooleanField(default=False)
    video_surveillance = models.BooleanField(default=False)
    private_garden = models.BooleanField(default=False)
    split_air_conditioning = models.BooleanField(default=False)
    gym = models.BooleanField(default=False)
    laundry_room = models.BooleanField(default=False)
    load_lifter = models.BooleanField(default=False)
    sauna = models.BooleanField(default=False)
    equipped_kitchen = models.BooleanField(default=False)
    service_door = models.BooleanField(default=False)
    storage_space = models.BooleanField(default=False)
    patio = models.BooleanField(default=False)
    solarium = models.BooleanField(default=False)
    curtain = models.BooleanField(default=False)
    playground = models.BooleanField(default=False)
    disabled_access = models.BooleanField(default=False)
    outdoor_parking = models.BooleanField(default=False)
    extraction_system = models.BooleanField(default=False)
    elevator = models.BooleanField(default=False)
    private_hammam = models.BooleanField(default=False)
    garden = models.BooleanField(default=False)
    wiring = models.BooleanField(default=False)
    cold_storage = models.BooleanField(default=False)
    private_swimming_pool = models.BooleanField(default=False)
    security_agent = models.BooleanField(default=False)
    underground_parking = models.BooleanField(default=False)
    terrace = models.BooleanField(default=False)
    emergency_exit = models.BooleanField(default=False)
    veranda = models.BooleanField(default=False)
    centralized_air_conditioning = models.BooleanField(default=False)
    gated_community = models.BooleanField(default=False)
    janitor = models.BooleanField(default=False)
    electric_water_heater = models.BooleanField(default=False)
    intercom = models.BooleanField(default=False)
    concierge = models.BooleanField(default=False)
    meeting_room = models.BooleanField(default=False)
    green_spaces = models.BooleanField(default=False)
    lobby = models.BooleanField(default=False)
    fireplace = models.BooleanField(default=False)
    fiber_installation = models.BooleanField(default=False)
    split_heating = models.BooleanField(default=False)
    gas_water_heater = models.BooleanField(default=False)
    maids_rooms = models.BooleanField(default=False)
    interior_patio = models.BooleanField(default=False)
    network_installation = models.BooleanField(default=False)
    basement = models.BooleanField(default=False)
    stove = models.BooleanField(default=False)
    centralized_heating = models.BooleanField(default=False)
    thermal_isolation = models.BooleanField(default=False)
    american_kitchen = models.BooleanField(default=False)
    balcony = models.BooleanField(default=False)
    domotique = models.BooleanField(default=False)
    garage = models.BooleanField(default=False)
    entry_code = models.BooleanField(default=False)
    pool = models.BooleanField(default=False)
    box = models.BooleanField(default=False)
    underground_parking_spaces = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    outdoor_parking_spaces = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    total_balcony_area = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    total_terrace_area = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    garden_area = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    solarium_area = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    garage_area = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    storage_area = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    box_area = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["property__yakeey_ref"]
        verbose_name = "Property Features"
        verbose_name_plural = "Property Features"

    def __str__(self) -> str:
        return f"Features for {self.property_id}"
