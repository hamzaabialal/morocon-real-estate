"""AI cover image generation via OpenAI DALL-E.

When OPENAI_API_KEY is set, this generates a cinematic property cover image
tailored to the listing's type, city, price tier, and area. The image is
downloaded immediately (DALL-E URLs expire ~1 hour) and saved under
MEDIA_ROOT/images/<property_id>/cover.png.

Tries models in order: $OPENAI_IMAGE_MODEL (default dall-e-3) → dall-e-2.
Service-account keys (sk-svcacct-*) often lack DALL-E access; in that case
both attempts fail and the media task falls back to a bundled placeholder.

Cost: dall-e-3 ~$0.04/image, dall-e-2 ~$0.02/image.
"""
import logging
from pathlib import Path

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)

MODEL_SIZES = {
    "dall-e-3": "1792x1024",
    "dall-e-2": "1024x1024",
}


def generate_cover_image(property_obj):
    """Generate, download, and persist an AI cover image. Returns local /media URL or None."""
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set; skipping AI cover generation.")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed; skipping AI cover generation.")
        return None

    prompt = build_prompt(property_obj)
    preferred_model = getattr(settings, "OPENAI_IMAGE_MODEL", "") or "dall-e-3"
    candidates = [preferred_model]
    if preferred_model != "dall-e-2":
        candidates.append("dall-e-2")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    image_bytes = None
    last_error = None
    for model in candidates:
        size = MODEL_SIZES.get(model, "1024x1024")
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                n=1,
            )
            temp_url = response.data[0].url
            logger.info("DALL-E (%s) succeeded for property %s", model, property_obj.id)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "DALL-E (%s) failed for property %s: %s", model, property_obj.id, exc
            )
            continue

        try:
            with httpx.Client(timeout=120.0, follow_redirects=True) as http_client:
                image_response = http_client.get(temp_url)
                image_response.raise_for_status()
                image_bytes = image_response.content
            break
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning("Could not download DALL-E result: %s", exc)
            continue

    if image_bytes is None:
        if last_error:
            logger.error(
                "AI cover generation gave up for property %s. Last error: %s. "
                "Hint: service-account OpenAI keys (sk-svcacct-*) often lack image-gen access; "
                "use a regular API key or grant the 'images:generate' scope.",
                property_obj.id, last_error,
            )
        return None

    media_root = Path(settings.MEDIA_ROOT)
    dest_dir = media_root / "images" / str(property_obj.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "cover.png"
    dest_path.write_bytes(image_bytes)

    media_url = settings.MEDIA_URL.rstrip("/")
    return f"{media_url}/images/{property_obj.id}/cover.png"


def build_prompt(property_obj):
    """Translate property data into a vivid DALL-E prompt."""
    parts = ["Cinematic professional real estate photograph,"]

    type_descriptors = {
        "VILLA":               "luxury Moroccan villa exterior with infinity pool and palm trees",
        "RIAD":                "traditional Moroccan riad interior courtyard with zellige tiles and fountain",
        "FLAT":                "modern bright apartment interior with floor-to-ceiling windows",
        "HOUSE":               "elegant contemporary Moroccan house facade",
        "OFFICE":              "sleek modern office space with city view",
        "TERRAIN":             "expansive Moroccan land plot with mountain or ocean backdrop",
        "COMMERCIAL_BUILDING": "modern commercial building entrance with glass facade",
    }
    parts.append(type_descriptors.get(property_obj.property_category, "premium Moroccan property"))

    city = getattr(property_obj.city, "name", "") if property_obj.city_id else ""
    if city:
        parts.append(f"in {city}, Morocco")
    if property_obj.neighborhood_id:
        neigh = getattr(property_obj.neighborhood, "name", "")
        if neigh:
            parts.append(f"({neigh} neighborhood)")

    price = float(property_obj.price or 0)
    if price >= 8_000_000:
        parts.append("ultra-luxury estate, ornate Andalusian architecture, marble, gold accents")
    elif price >= 3_000_000:
        parts.append("upscale contemporary design, natural stone, manicured gardens")
    elif price >= 1_000_000:
        parts.append("warm Moroccan modernism, white walls, wooden accents")
    else:
        parts.append("comfortable, well-maintained, sunny")

    if property_obj.bedrooms and property_obj.bedrooms >= 4:
        parts.append("spacious multi-room layout")
    if property_obj.area and float(property_obj.area) >= 200:
        parts.append("expansive interior")

    if property_obj.transaction_type == "RENT":
        parts.append("inviting, ready to move in")

    parts.append(
        "golden hour lighting, ultra-realistic, 8k architectural photography, "
        "Architectural Digest editorial style, no people, no text or watermarks"
    )

    return ", ".join(parts)
