"""OpenAI-powered caption generation for property listings."""
import json
import logging
import re

from django.conf import settings


logger = logging.getLogger(__name__)


CAPTION_SYSTEM_PROMPT = (
    "You are a real estate copywriter for the Moroccan market. Generate engaging "
    "property listing captions in the requested language. Always include price, "
    "area, and neighborhood. Keep Instagram captions under 150 characters. "
    "Include 10 relevant hashtags. Respond in JSON with keys: caption_fr, "
    "caption_ar, hashtags, headline."
)


def generate_captions(property_obj):
    """Generate French and Arabic captions for a property using OpenAI."""
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY is not configured; skipping caption generation.")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.exception("OpenAI SDK is not installed.")
        return None

    payload = {
        "price": f"{property_obj.price} {property_obj.currency}",
        "area": f"{property_obj.area} m2",
        "bedrooms": property_obj.bedrooms,
        "neighborhood": str(property_obj.neighborhood) if property_obj.neighborhood else "",
        "city": str(property_obj.city) if property_obj.city else "",
        "property_type": property_obj.get_property_type_display()
        or property_obj.property_type,
    }

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": CAPTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Generate captions for this Moroccan property listing. "
                        f"Property data: {json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
            temperature=0.7,
        )
        content = response.choices[0].message.content or ""
        parsed = parse_json_response(content)
        if not parsed:
            return None
        return {
            "caption_fr": parsed.get("caption_fr", ""),
            "caption_ar": parsed.get("caption_ar", ""),
            "hashtags": normalize_hashtags(parsed.get("hashtags")),
            "headline": parsed.get("headline", ""),
        }
    except Exception:
        logger.exception("Caption generation failed for property %s", property_obj.id)
        return None


def normalize_hashtags(value):
    """Return a list of hashtag strings regardless of what shape the model returned."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str):
        tokens = re.findall(r"#\w+", value)
        if tokens:
            return tokens
        return [token.strip() for token in value.split() if token.strip()]
    return []


def parse_json_response(content):
    """Parse a JSON response, accepting fenced JSON blocks as well."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
