"""Tests for individual Sarouty listing parsing."""
from decimal import Decimal

from apps.scraper.listing_parser import parse_listing_html


def test_parse_listing_html_extracts_core_fields():
    html = """
    <html>
      <head>
        <meta property="og:latitude" content="33.573100">
        <meta property="og:longitude" content="-7.589800">
      </head>
      <body>
        <nav><a>Casablanca</a><a>Maarif</a></nav>
        <h1>Appartement a vendre</h1>
        <div class="price">1 250 000 DH</div>
        <div class="details">92 m² 3 chambres 2 salles de bain étage 4/5</div>
        <div class="description">Bel appartement lumineux avec terrasse.</div>
        <div class="features"><span>Ascenseur</span><span>Terrasse</span></div>
        <img src="/media/listing/photo-1.jpg">
        <section class="agency">
          <span class="name">Best Home</span>
          <img alt="agency logo" src="/logos/best-home.png">
          <a href="/trouver-une-agence/best-home">Agency</a>
        </section>
        <a href="https://wa.me/212612345678">WhatsApp</a>
        <p>Contact: 0612345678</p>
      </body>
    </html>
    """

    listing = parse_listing_html(html, 902701)

    assert listing is not None
    assert listing.sarouty_id == 902701
    assert listing.price == Decimal("1250000")
    assert listing.area == Decimal("92")
    assert listing.rooms == 3
    assert listing.bathrooms == 2
    assert listing.floor == 4
    assert listing.total_floors == 5
    assert listing.latitude == Decimal("33.573100")
    assert listing.longitude == Decimal("-7.589800")
    assert "terrasse" in listing.amenities
    assert listing.agency_phone == "0612345678"
    assert listing.agency_whatsapp == "212612345678"


def test_parse_listing_html_returns_none_when_no_price_or_area():
    assert parse_listing_html("<html><body>not found</body></html>", 1) is None


def test_parse_listing_html_returns_none_for_unavailable_page():
    html = "<html><body>Property not available</body></html>"

    assert parse_listing_html(html, 902701) is None
