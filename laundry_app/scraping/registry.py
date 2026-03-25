"""Source registry, parser registry, and workbook alias hints."""

from __future__ import annotations

from laundry_app.scraping.church_dwight import scrape as scrape_church_dwight
from laundry_app.scraping.dirtylabs import scrape as scrape_dirtylabs
from laundry_app.scraping.dropps import scrape as scrape_dropps
from laundry_app.scraping.ecos import scrape as scrape_ecos
from laundry_app.scraping.models import SourceSeed
from laundry_app.scraping.product_pages import scrape_clorox, scrape_tide
from laundry_app.scraping.sprouts import scrape as scrape_sprouts
from laundry_app.scraping.wholefoods import scrape as scrape_wholefoods


SCRAPER_REGISTRY = {
    "church_dwight": scrape_church_dwight,
    "wholefoods": scrape_wholefoods,
    "sprouts": scrape_sprouts,
    "ecos": scrape_ecos,
    "dirtylabs": scrape_dirtylabs,
    "dropps": scrape_dropps,
    "tide": scrape_tide,
    "clorox": scrape_clorox,
}


SOURCE_SEEDS: list[SourceSeed] = [
    SourceSeed(
        family="church_dwight",
        url="https://churchdwight.com/ingredient-disclosure/laundry-fabric-care/40501171-oxiclean-white-revive-whitener-and-stain-remover.aspx",
        source_type="disclosure",
        notes="Verified Church & Dwight disclosure page for OxiClean White Revive.",
        target_products=("OxiClean White Revive",),
    ),
    SourceSeed(
        family="church_dwight",
        url="https://churchdwight.com/ingredient-disclosure/laundry-fabric-care/42015223-Oxiclean-Laundry-Stain-Remover-Free.aspx",
        source_type="disclosure",
        notes="Verified Church & Dwight disclosure page for the free OxiClean stain remover variant.",
        target_products=("OxiClean Versatile Free",),
    ),
    SourceSeed(
        family="wholefoods",
        url="https://wfm.amazon.com/legal/liquid-laundry-detergent-disclosure",
        source_type="disclosure",
        target_products=(
            "365 by Whole Foods Concentrated",
            "365 By Whole Foods Sport",
        ),
    ),
    SourceSeed(
        family="wholefoods",
        url="https://wfm.amazon.com/legal/powdered-laundry-detergent-disclosure",
        source_type="disclosure",
        target_products=("365 By Whole Foods Unscented Powder",),
    ),
    SourceSeed(
        family="wholefoods",
        url="https://wfm.amazon.com/legal/laundry-detergent-packs-disclosure",
        source_type="disclosure",
        target_products=(),
    ),
    SourceSeed(
        family="wholefoods",
        url="https://wfm.amazon.com/legal/laundry-treatments-prewash-disclosure",
        source_type="disclosure",
        target_products=(
            "365 By Whole Foods Stain Remover",
            "365 Oxygen Whitener",
        ),
    ),
    SourceSeed(
        family="sprouts",
        url="https://www.sprouts.com/california-cleaning-product-right-to-know-act/",
        source_type="disclosure",
        target_products=(
            "Sprouts Liquid Laundry Detergent",
            "Sprouts Laundry Stain Remover",
            "Sprouts Oxygen Brightener",
        ),
    ),
    SourceSeed(
        family="ecos",
        url="https://www.ecos.com/laundry/laundry-detergent-ultra-concentrated-free-clear/",
        source_type="product_page",
        target_products=("ECOS Laundry Detergent With Enzymes",),
    ),
    SourceSeed(
        family="dirtylabs",
        url="https://dirtylabs.com/products/bio-enzyme-laundry-booster",
        source_type="product_page",
        target_products=("Dirty Labs Bio Enzyme Laundry Booster",),
    ),
    SourceSeed(
        family="dropps",
        url="https://www.dropps.com/pages/ingredient-disclosure-4-in-1-plus-oxi-laundry-detergent-unscented",
        source_type="disclosure",
        target_products=("Dropps 4-in-1 Plus Oxi",),
    ),
    SourceSeed(
        family="dropps",
        url="https://www.dropps.com/pages/ingredient-disclosure-stain-odor-laundry-detergent-unscented",
        source_type="disclosure",
        target_products=("Dropps Free & Clear",),
    ),
    SourceSeed(
        family="tide",
        url="https://tide.com/en-us/shop/type/liquid/tide-free-and-gentle-liquid",
        source_type="product_page",
        target_products=("Tide Clean & Gentle",),
    ),
    SourceSeed(
        family="tide",
        url="https://tide.com/en-us/shop/type/liquid/tide-ultra-oxi-he-liquid",
        source_type="product_page",
        target_products=("Tide + Ultra Oxi",),
    ),
    SourceSeed(
        family="tide",
        url="https://tide.com/en-us/shop/type/powder/tide-plus-bleach-powder",
        source_type="product_page",
        target_products=("Tide with Bleach",),
    ),
    SourceSeed(
        family="tide",
        url="https://tide.com/en-us/shop/type/powder/tide-original-powder",
        source_type="product_page",
        target_products=("Tide (All Other Powders)",),
    ),
    SourceSeed(
        family="clorox",
        url="https://www.clorox.com/products/clorox-2-for-colors-3-in-1-liquid/original-scent/",
        source_type="product_page",
        target_products=("Clorox 2 for Colors",),
    ),
    SourceSeed(
        family="clorox",
        url="https://www.clorox.com/products/clorox-2-for-colors-3-in-1-liquid/clean-linen/",
        source_type="product_page",
        target_products=("Clorox 2 for Colors",),
    ),
    SourceSeed(
        family="clorox",
        url="https://www.clorox.com/products/clorox2-for-colors-free-clear-max-performance-stain-remover-and-laundry-additive/",
        source_type="product_page",
        target_products=("Clorox 2 for Colors Max Performance",),
    ),
]


PRODUCT_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "church_dwight": {
        "OxiClean White Revive": ("OxiClean White Revive Whitener and Stain Remover",),
        "OxiClean Versatile Free": (
            "OxiClean Laundry Stain Remover Free",
            "OxiClean Stain Remover Free",
        ),
    },
    "wholefoods": {
        "365 by Whole Foods Concentrated": (
            "Concentrated Laundry Detergent",
            "Laundry Detergent 2x Concentrated",
        ),
        "365 By Whole Foods Sport": ("Sport Laundry Detergent",),
        "365 By Whole Foods Unscented Powder": (
            "Powder Laundry Detergent",
            "Powdered Laundry Detergent",
            "Free & Clear Powdered Laundry Detergent",
        ),
        "365 By Whole Foods Stain Remover": ("Stain Remover & Prewash",),
        "365 Oxygen Whitener": ("Oxygen Whitening Powder",),
    },
    "sprouts": {
        "Sprouts Liquid Laundry Detergent": ("Liquid Laundry Detergent",),
        "Sprouts Laundry Stain Remover": ("Laundry Stain Remover",),
        "Sprouts Oxygen Brightener": ("Oxygen Brightener",),
    },
    "ecos": {
        "ECOS Laundry Detergent With Enzymes": (
            "Laundry Detergent Ultra-Concentrated Free & Clear",
            "Hypoallergenic Laundry Detergent – Free & Clear",
            "Hypoallergenic Laundry Detergent with Enzymes",
        ),
    },
    "dirtylabs": {
        "Dirty Labs Bio Enzyme Laundry Booster": ("Bio Enzyme Laundry Booster",),
    },
    "dropps": {
        "Dropps 4-in-1 Plus Oxi": ("4-in-1 Plus Oxi Laundry Detergent",),
        "Dropps Free & Clear": ("Free & Clear Laundry Detergent",),
        "Dropps Odor+Stain": (
            "Odor + Stain Laundry Detergent",
            "Stain + Odor Laundry Detergent",
        ),
        "Dropps Oxi Booster": ("Oxi Booster",),
        "Dropps Odor Eraser": ("Odor Eraser",),
    },
    "tide": {
        "Tide Clean & Gentle": (
            "Tide Free and Gentle Liquid Laundry Detergent",
            "Tide Free & Gentle Liquid Laundry Detergent",
            "Tide Free & Gentle",
        ),
        "Tide + Ultra Oxi": (
            "Tide Ultra OXI Boost High Efficiency Liquid Laundry Detergent",
            "Tide Ultra OXI Boost",
        ),
        "Tide with Bleach": ("Tide Plus Bleach Powder Laundry Detergent",),
        "Tide (All Other Powders)": ("Tide Original Powder Laundry Detergent",),
    },
    "clorox": {
        "Clorox 2 for Colors": (
            "Clorox 2 for Colors Bleach-Free Laundry Stain & Odor Remover Liquid",
            "Clorox 2 for Colors 3-in-1 Laundry Additive",
            "Clorox 2 Laundry Stain Remover and Color Booster",
        ),
        "Clorox 2 for Colors Max Performance": (
            "Clorox 2 for Colors Free & Clear Max Performance Stain Remover",
            "Clorox 2 Free & Clear Max Performance Stain Remover",
        ),
    },
}
