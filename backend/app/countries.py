"""Country list: CZ first, SK second, then alphabetically by English name."""

import pycountry

# Priority ISO codes
_FIRST = ("CZ", "SK")


def get_country_options() -> list[dict[str, str]]:
    """Return [{code, name_en}, ...] for select UI."""
    all_codes = {c.alpha_2 for c in pycountry.countries}
    rest = sorted(
        (c for c in all_codes if c not in _FIRST),
        key=lambda code: pycountry.countries.get(alpha_2=code).name,
    )
    ordered = list(_FIRST) + rest
    out: list[dict[str, str]] = []
    for code in ordered:
        c = pycountry.countries.get(alpha_2=code)
        if c:
            out.append({"code": code, "name_en": c.name})
    return out
