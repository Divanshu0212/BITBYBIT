"""
Design Metrics — Lightweight Deterministic Signal Extraction
────────────────────────────────────────────────────────────
Compute design-specific quality signals from submission text and URLs
before sending to the LLM.  All computation is pure string/regex analysis
(zero heavy dependencies), safe for an 8 GB VPS.

Optional Figma API enrichment adds metadata like page/frame counts
without downloading images — just a single lightweight JSON endpoint.
"""

import logging
import re
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# ── Design Tool URL Patterns ────────────────────────────────────────────

_DESIGN_TOOL_PATTERNS: dict[str, re.Pattern] = {
    "figma": re.compile(r"https?://(www\.)?figma\.com/(file|design|proto)/([a-zA-Z0-9]+)", re.IGNORECASE),
    "figma_prototype": re.compile(r"https?://(www\.)?figma\.com/proto/([a-zA-Z0-9]+)", re.IGNORECASE),
    "dribbble": re.compile(r"https?://(www\.)?dribbble\.com/shots/\d+", re.IGNORECASE),
    "behance": re.compile(r"https?://(www\.)?behance\.net/gallery/\d+", re.IGNORECASE),
    "invision": re.compile(r"https?://([a-z]+\.)?invisionapp\.com/", re.IGNORECASE),
    "zeplin": re.compile(r"https?://app\.zeplin\.io/", re.IGNORECASE),
    "adobe_xd": re.compile(r"https?://xd\.adobe\.com/", re.IGNORECASE),
    "canva": re.compile(r"https?://(www\.)?canva\.com/design/", re.IGNORECASE),
    "sketch_cloud": re.compile(r"https?://(www\.)?sketch\.com/s/", re.IGNORECASE),
}

_EXPORT_FORMATS_DOT = re.compile(
    r"\.(png|jpg|jpeg|svg|pdf|fig|sketch|xd|ai|psd|webp|eps|tiff?|ico|gif)\b",
    re.IGNORECASE,
)
_EXPORT_FORMATS_STANDALONE = re.compile(
    r"\b(png|jpg|jpeg|svg|pdf|psd|webp|eps|tiff|sketch|xd|figma)\b",
    re.IGNORECASE,
)

_ACCESSIBILITY_PATTERNS = re.compile(
    r"\b(accessibility|a11y|alt[\s\-]?text|aria[\s\-]?label|wcag|contrast[\s\-]?ratio|"
    r"screen[\s\-]?reader|keyboard[\s\-]?nav|color[\s\-]?blind|focus[\s\-]?state|"
    r"tab[\s\-]?order|skip[\s\-]?link|semantic|landmark|role=)\b",
    re.IGNORECASE,
)

_RESPONSIVE_PATTERNS = re.compile(
    r"\b(responsive|mobile|tablet|desktop|breakpoint|viewport|media[\s\-]?query|"
    r"adaptive|fluid[\s\-]?grid|flexible[\s\-]?layout|portrait|landscape|"
    r"320px|375px|768px|1024px|1440px|small[\s\-]?screen|large[\s\-]?screen)\b",
    re.IGNORECASE,
)

_COLOR_PATTERNS = re.compile(
    r"(#[0-9a-fA-F]{3,8}\b|rgb\(|rgba\(|hsl\(|hsla\(|"
    r"\b(color[\s\-]?palette|brand[\s\-]?color|primary[\s\-]?color|"
    r"secondary[\s\-]?color|accent[\s\-]?color|color[\s\-]?scheme|"
    r"color[\s\-]?system|dark[\s\-]?mode|light[\s\-]?mode|theme)\b)",
    re.IGNORECASE,
)

_TYPOGRAPHY_PATTERNS = re.compile(
    r"\b(font[\s\-]?family|typeface|typography|font[\s\-]?size|font[\s\-]?weight|"
    r"line[\s\-]?height|letter[\s\-]?spacing|heading[\s\-]?style|body[\s\-]?text|"
    r"type[\s\-]?scale|inter|roboto|poppins|helvetica|arial|open[\s\-]?sans|"
    r"montserrat|lato|nunito|playfair|serif|sans[\s\-]?serif|monospace)\b",
    re.IGNORECASE,
)

_SCREEN_PATTERNS = re.compile(
    r"\b(screen|page|view|layout|frame|artboard|canvas|slide|mockup|wireframe|"
    r"prototype|flow|user[\s\-]?flow|sitemap|dashboard|landing[\s\-]?page|"
    r"home[\s\-]?page|login|signup|register|profile|settings|onboarding|"
    r"checkout|cart|product|detail|list[\s\-]?view|modal|dialog|navbar|"
    r"sidebar|footer|header|hero|404|error[\s\-]?page|empty[\s\-]?state|"
    r"loading[\s\-]?state|splash)\b",
    re.IGNORECASE,
)

_COMPONENT_PATTERNS = re.compile(
    r"\b(button|input|form|card|icon|avatar|badge|tooltip|dropdown|"
    r"select|checkbox|radio|toggle|switch|slider|tab|accordion|"
    r"breadcrumb|pagination|progress[\s\-]?bar|spinner|skeleton|"
    r"alert|toast|notification|chip|tag|divider|stepper|"
    r"carousel|gallery|table|data[\s\-]?grid|search[\s\-]?bar|"
    r"navigation|menu|bottom[\s\-]?nav|fab|snackbar)\b",
    re.IGNORECASE,
)

_DESIGN_SYSTEM_PATTERNS = re.compile(
    r"\b(design[\s\-]?system|component[\s\-]?library|style[\s\-]?guide|"
    r"pattern[\s\-]?library|ui[\s\-]?kit|token|spacing[\s\-]?scale|"
    r"grid[\s\-]?system|8[\s\-]?px[\s\-]?grid|4[\s\-]?px[\s\-]?grid|"
    r"atomic[\s\-]?design|design[\s\-]?token|figma[\s\-]?library|"
    r"material[\s\-]?design|human[\s\-]?interface)\b",
    re.IGNORECASE,
)


# ── Public API ───────────────────────────────────────────────────────────

def compute_design_metrics(
    submission: str,
    required_screens: list[str] | None = None,
    required_components: list[str] | None = None,
) -> dict:
    """
    Compute all design metrics from submission text.
    Pure string/regex analysis — zero external calls.
    """
    all_urls = re.findall(r"https?://[^\s)<>\"]+", submission)

    design_tool_urls = _extract_design_tool_urls(submission)
    export_formats = _extract_export_formats(submission)
    a11y_hits = len(_ACCESSIBILITY_PATTERNS.findall(submission))
    responsive_hits = len(_RESPONSIVE_PATTERNS.findall(submission))
    color_hits = len(_COLOR_PATTERNS.findall(submission))
    typography_hits = len(_TYPOGRAPHY_PATTERNS.findall(submission))
    screen_mentions = set(m.lower() for m in _SCREEN_PATTERNS.findall(submission))
    component_mentions = set(m.lower() for m in _COMPONENT_PATTERNS.findall(submission))
    design_system_hits = len(_DESIGN_SYSTEM_PATTERNS.findall(submission))

    screen_coverage = _compute_screen_coverage(submission, required_screens)
    component_coverage = _compute_component_coverage(submission, required_components)

    return {
        "total_urls": len(all_urls),
        "design_tool_urls": design_tool_urls,
        "design_tool_count": len(design_tool_urls),
        "export_formats": export_formats,
        "export_format_count": len(export_formats),
        "accessibility_signal_count": a11y_hits,
        "responsive_signal_count": responsive_hits,
        "color_spec_count": color_hits,
        "typography_spec_count": typography_hits,
        "screen_mention_count": len(screen_mentions),
        "component_mention_count": len(component_mentions),
        "design_system_signal_count": design_system_hits,
        "screen_coverage": screen_coverage,
        "component_coverage": component_coverage,
        "word_count": len(submission.split()),
    }


# ── Figma API Enrichment (optional, lightweight) ────────────────────────

async def fetch_figma_metadata(
    figma_url: str,
    token: str,
    timeout: float = 10.0,
) -> dict | None:
    """
    Fetch lightweight metadata from the Figma API.
    Returns page count, frame count, component names — no image downloads.
    Memory-safe: just a small JSON response (~2-20 KB).
    """
    file_key = _extract_figma_file_key(figma_url)
    if not file_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"https://api.figma.com/v1/files/{file_key}?depth=2",
                headers={"X-Figma-Token": token},
            )
            if resp.status_code != 200:
                logger.warning(f"Figma API returned {resp.status_code} for {file_key}")
                return None

            data = resp.json()
            return _parse_figma_response(data)

    except Exception as exc:
        logger.warning(f"Figma API call failed: {exc}")
        return None


def _extract_figma_file_key(url: str) -> str | None:
    match = _DESIGN_TOOL_PATTERNS["figma"].search(url)
    if match:
        return match.group(3)
    return None


def _parse_figma_response(data: dict) -> dict:
    """Extract useful metadata from Figma file response."""
    document = data.get("document", {})
    pages = document.get("children", [])

    frames = []
    components = []
    for page in pages:
        for child in page.get("children", []):
            child_type = child.get("type", "")
            if child_type in ("FRAME", "COMPONENT", "COMPONENT_SET"):
                frames.append(child.get("name", ""))
            if child_type in ("COMPONENT", "COMPONENT_SET"):
                components.append(child.get("name", ""))

    return {
        "file_name": data.get("name", ""),
        "last_modified": data.get("lastModified", ""),
        "page_count": len(pages),
        "page_names": [p.get("name", "") for p in pages],
        "frame_count": len(frames),
        "frame_names": frames[:50],
        "component_count": len(components),
        "component_names": components[:50],
    }


# ── Internal Helpers ─────────────────────────────────────────────────────

def _extract_design_tool_urls(text: str) -> list[dict]:
    """Find all recognised design tool URLs with their platform."""
    results = []
    seen = set()
    for platform, pattern in _DESIGN_TOOL_PATTERNS.items():
        for match in pattern.finditer(text):
            url = match.group(0)
            if url not in seen:
                seen.add(url)
                results.append({"platform": platform, "url": url})
    return results


def _extract_export_formats(text: str) -> list[str]:
    """Find all mentioned design export file formats (dotted and standalone)."""
    dotted = set(m.lower() for m in _EXPORT_FORMATS_DOT.findall(text))
    standalone = set(m.lower() for m in _EXPORT_FORMATS_STANDALONE.findall(text))
    return list(dotted | standalone)


def _compute_screen_coverage(text: str, required_screens: list[str] | None) -> float:
    """Fraction of required screens mentioned in the submission."""
    if not required_screens:
        return 1.0
    text_lower = text.lower()
    found = sum(1 for s in required_screens if s.lower() in text_lower)
    return round(found / len(required_screens), 3)


def _compute_component_coverage(text: str, required_components: list[str] | None) -> float:
    """Fraction of required components mentioned in the submission."""
    if not required_components:
        return 1.0
    text_lower = text.lower()
    found = sum(1 for c in required_components if c.lower() in text_lower)
    return round(found / len(required_components), 3)
