"""Design tokens (see UI_DESIGN.md). Widgets never contain raw colors; they use these."""

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Tokens:
    primary: str
    primary_hover: str
    on_primary: str
    accent: str
    on_accent: str
    destructive: str
    background: str
    surface: str
    surface_muted: str
    foreground: str
    muted_foreground: str
    border: str
    success: str
    warning: str
    selection: str

    def as_dict(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# Light primary is teal-700 rather than teal-600: white text on teal-600 is only 3.7:1.
LIGHT = Tokens(
    primary="#0F766E",
    primary_hover="#115E59",
    on_primary="#FFFFFF",
    accent="#C2410C",
    on_accent="#FFFFFF",
    destructive="#DC2626",
    background="#F8FAFC",
    surface="#FFFFFF",
    surface_muted="#F1F5F9",
    foreground="#0F172A",
    muted_foreground="#475569",
    border="#E2E8F0",
    success="#15803D",
    warning="#B45309",
    selection="#CCFBF1",
)

DARK = Tokens(
    primary="#14B8A6",
    primary_hover="#2DD4BF",
    on_primary="#0F172A",
    accent="#FB923C",
    on_accent="#0F172A",
    destructive="#F87171",
    background="#0F172A",
    surface="#1E293B",
    surface_muted="#273449",
    foreground="#E2E8F0",
    muted_foreground="#94A3B8",
    border="#334155",
    success="#4ADE80",
    warning="#FBBF24",
    selection="#134E4A",
)

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
RADIUS_CONTROL = 6
RADIUS_CARD = 10
CONTROL_HEIGHT = 32
PRIMARY_HEIGHT = 36

FONT_FAMILY = "Inter"
FALLBACK_FONT = "Segoe UI"
FONT_CAPTION = 12
FONT_BODY = 14
FONT_SECTION = 16
FONT_TITLE = 20


def relative_luminance(color: str) -> float:
    value = color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a: str, b: str) -> float:
    high, low = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)
