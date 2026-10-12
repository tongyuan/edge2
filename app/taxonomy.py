from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.validation import normalize_symbol


ASSET_CLASSES = frozenset({
    "EQUITY",
    "ETF",
    "INDEX",
    "CRYPTO",
    "COMMODITY",
    "FX",
})

# Internally maintained, GICS-compatible labels. These are not licensed or
# represented as official GICS assignments.
EQUITY_INDUSTRIES_BY_SECTOR: Mapping[str, frozenset[str]] = {
    "Communication Services": frozenset({
        "Diversified Telecommunication Services",
        "Entertainment",
        "Interactive Media & Services",
        "Media",
        "Wireless Telecommunication Services",
    }),
    "Consumer Discretionary": frozenset({
        "Automobiles",
        "Broadline Retail",
        "Consumer Discretionary Distribution & Retail",
        "Hotels, Restaurants & Leisure",
        "Household Durables",
        "Leisure Products",
        "Textiles, Apparel & Luxury Goods",
    }),
    "Consumer Staples": frozenset({
        "Beverages",
        "Consumer Staples Distribution & Retail",
        "Food Products",
        "Household Products",
        "Personal Care Products",
        "Tobacco",
    }),
    "Energy": frozenset({
        "Energy Equipment & Services",
        "Oil & Gas",
    }),
    "Financials": frozenset({
        "Banks",
        "Capital Markets",
        "Consumer Finance",
        "Financial Services",
        "Insurance",
        "Mortgage REITs",
    }),
    "Health Care": frozenset({
        "Biotechnology",
        "Health Care Equipment & Supplies",
        "Health Care Providers & Services",
        "Health Care Technology",
        "Life Sciences Tools & Services",
        "Managed Health Care",
        "Pharmaceuticals",
    }),
    "Industrials": frozenset({
        "Aerospace & Defense",
        "Building Products",
        "Commercial Services & Supplies",
        "Construction & Engineering",
        "Electrical Equipment",
        "Ground Transportation",
        "Industrial Conglomerates",
        "Machinery",
        "Passenger Airlines",
        "Professional Services",
        "Trading Companies & Distributors",
    }),
    "Materials": frozenset({
        "Chemicals",
        "Construction Materials",
        "Containers & Packaging",
        "Metals & Mining",
        "Paper & Forest Products",
    }),
    "Real Estate": frozenset({
        "Equity REITs",
        "Real Estate Management & Development",
    }),
    "Technology": frozenset({
        "Communications Equipment",
        "Electronic Equipment, Instruments & Components",
        "IT Services",
        "Semiconductors",
        "Software",
        "Technology Hardware, Storage & Peripherals",
    }),
    "Utilities": frozenset({
        "Electric Utilities",
        "Gas Utilities",
        "Independent Power and Renewable Electricity Producers",
        "Multi-Utilities",
        "Water Utilities",
    }),
}

EQUITY_SECTORS = frozenset(EQUITY_INDUSTRIES_BY_SECTOR)


class TaxonomyValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class InstrumentTaxonomy:
    symbol: str
    asset_class: str | None
    sector: str | None
    industry: str | None

    @property
    def complete(self) -> bool:
        if self.asset_class is None:
            return False
        if self.asset_class == "EQUITY":
            return self.sector is not None and self.industry is not None
        return self.sector is None and self.industry is None

    def payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "sector": self.sector,
            "industry": self.industry,
            "taxonomy_complete": self.complete,
        }


def optional_text(value: Any) -> str | None:
    text = " ".join(str(value or "").strip().split())
    return text or None


def validate_instrument_taxonomy(
    *,
    symbol: Any,
    asset_class: Any = None,
    sector: Any = None,
    industry: Any = None,
    require_complete_equity: bool = False,
) -> InstrumentTaxonomy:
    normalized_symbol = normalize_symbol(symbol)
    normalized_asset_class = optional_text(asset_class)
    if normalized_asset_class is not None:
        normalized_asset_class = normalized_asset_class.upper()
    normalized_sector = optional_text(sector)
    normalized_industry = optional_text(industry)

    if normalized_asset_class not in ASSET_CLASSES and normalized_asset_class is not None:
        raise TaxonomyValidationError(
            f"asset_class must be one of: {', '.join(sorted(ASSET_CLASSES))}"
        )
    if normalized_industry is not None and normalized_sector is None:
        raise TaxonomyValidationError("industry requires sector")
    if normalized_asset_class != "EQUITY":
        if normalized_sector is not None or normalized_industry is not None:
            raise TaxonomyValidationError(
                "sector and industry are valid only for EQUITY instruments"
            )
    else:
        if normalized_sector is not None and normalized_sector not in EQUITY_SECTORS:
            raise TaxonomyValidationError(
                f"sector must be one of: {', '.join(sorted(EQUITY_SECTORS))}"
            )
        if normalized_industry is not None:
            allowed_industries = EQUITY_INDUSTRIES_BY_SECTOR.get(
                normalized_sector or "", frozenset()
            )
            if normalized_industry not in allowed_industries:
                raise TaxonomyValidationError(
                    f"industry is not valid for sector {normalized_sector!r}"
                )
        if require_complete_equity and (
            normalized_sector is None or normalized_industry is None
        ):
            raise TaxonomyValidationError(
                "EQUITY import rows require both sector and industry"
            )

    return InstrumentTaxonomy(
        symbol=normalized_symbol,
        asset_class=normalized_asset_class,
        sector=normalized_sector,
        industry=normalized_industry,
    )


def instrument_taxonomy_from_row(row: Mapping[str, Any] | None, symbol: str) -> InstrumentTaxonomy:
    if row is None:
        return InstrumentTaxonomy(symbol=normalize_symbol(symbol), asset_class=None, sector=None, industry=None)
    return InstrumentTaxonomy(
        symbol=normalize_symbol(row["symbol"]),
        asset_class=optional_text(row.get("asset_class")),
        sector=optional_text(row.get("sector")),
        industry=optional_text(row.get("industry")),
    )
