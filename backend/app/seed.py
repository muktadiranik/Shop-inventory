"""Repeatable, additive demo inventory. Run: python -m app.seed.

Historical movements are inserted with their original timestamps, never edited.
This is a database maintenance command, not an application data API.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from random import Random
import sqlite3

from sqlalchemy import select

from app.config import DATABASE_PATH
from app.database import Database
from app.models import Product, StockMovement
from app.services.common import clean_sku, clean_text, integer
from app.services.products import canonical_category, validated_fields
from app.services.reporting import dashboard

# Prices are integer minor units in the app's existing two-decimal shop currency.
# Product quantities count individual packs/bottles, never fractional kilograms.
CATALOG = [
    ("GRA", "Rice, Flour & Grains", "Pantry Wholesale", [
        ("Long Grain Rice 1 kg", 249), ("Basmati Rice 1 kg", 399),
        ("Brown Rice 1 kg", 329), ("Jasmine Rice 1 kg", 349),
        ("All-Purpose Flour 1 kg", 179), ("Whole Wheat Flour 1 kg", 219),
        ("Rolled Oats 500 g", 249), ("Fine Semolina 500 g", 149),
        ("Corn Flour 500 g", 159), ("Pearl Barley 500 g", 199),
    ]),
    ("PLS", "Pulses & Beans", "Pantry Wholesale", [
        ("Red Lentils 500 g", 189), ("Green Lentils 500 g", 209),
        ("Chickpeas 500 g", 199), ("Red Kidney Beans 500 g", 229),
        ("Black Beans 500 g", 219), ("White Beans 500 g", 209),
        ("Split Peas 500 g", 169), ("Mung Beans 500 g", 239),
        ("Yellow Lentils 500 g", 179), ("Mixed Soup Beans 500 g", 249),
    ]),
    ("CKG", "Cooking Essentials", "Pantry Wholesale", [
        ("Sunflower Oil 1 L", 399), ("Vegetable Oil 1 L", 349),
        ("Extra Virgin Olive Oil 500 mL", 699), ("Table Salt 1 kg", 99),
        ("White Sugar 1 kg", 179), ("Brown Sugar 500 g", 199),
        ("White Vinegar 500 mL", 149), ("Soy Sauce 250 mL", 229),
        ("Baking Powder 100 g", 129), ("Corn Starch 200 g", 139),
    ]),
    ("SPC", "Spices & Seasonings", "Market Spice Supply", [
        ("Ground Turmeric 100 g", 159), ("Ground Cumin 100 g", 219),
        ("Ground Coriander 100 g", 189), ("Chili Powder 100 g", 179),
        ("Black Pepper 50 g", 249), ("Cinnamon Sticks 50 g", 199),
        ("Dried Oregano 20 g", 149), ("Mixed Herbs 20 g", 159),
        ("Paprika 100 g", 229), ("Whole Cloves 30 g", 189),
    ]),
    ("PKG", "Packaged Foods", "Corner Shop Distributors", [
        ("Digestive Biscuits 250 g", 189), ("Cream Crackers 200 g", 149),
        ("Chocolate Cookies 150 g", 199), ("Instant Noodles 5 Pack", 249),
        ("Spaghetti Pasta 500 g", 159), ("Penne Pasta 500 g", 169),
        ("Tomato Passata 500 g", 199), ("Canned Sweetcorn 340 g", 139),
        ("Peanut Butter 340 g", 329), ("Strawberry Jam 300 g", 279),
    ]),
    ("BEV", "Beverages", "Everyday Beverage Supply", [
        ("Black Tea 80 Bags", 349), ("Green Tea 25 Bags", 299),
        ("Instant Coffee 100 g", 449), ("Ground Coffee 250 g", 599),
        ("Hot Chocolate 250 g", 329), ("Orange Juice 1 L", 249),
        ("Apple Juice 1 L", 229), ("Cola 1.5 L", 199),
        ("Sparkling Water 1 L", 119), ("Still Water 1.5 L", 99),
    ]),
    ("DRY", "Dairy & Chilled", "Morning Dairy Delivery", [
        ("Whole Milk 1 L", 139), ("Semi-Skimmed Milk 1 L", 135),
        ("Skimmed Milk 1 L", 135), ("Plain Yogurt 500 g", 189),
        ("Greek Yogurt 400 g", 279), ("Salted Butter 250 g", 249),
        ("Unsalted Butter 250 g", 249), ("Cheddar Cheese 200 g", 299),
        ("Mozzarella Cheese 125 g", 199), ("Fresh Cream 250 mL", 179),
    ]),
    ("CLN", "Household Cleaning", "Homecare Wholesale", [
        ("Dishwashing Liquid 500 mL", 179), ("Laundry Powder 1 kg", 449),
        ("Laundry Liquid 1 L", 499), ("Fabric Conditioner 1 L", 329),
        ("Floor Cleaner 1 L", 279), ("Glass Cleaner 500 mL", 229),
        ("Toilet Cleaner 750 mL", 249), ("Disinfectant 500 mL", 299),
        ("Kitchen Degreaser 500 mL", 349), ("Bleach 1 L", 149),
    ]),
    ("CAR", "Personal Care", "Everyday Care Distributors", [
        ("Soap Bar 100 g", 99), ("Hand Wash 250 mL", 199),
        ("Shampoo 400 mL", 399), ("Conditioner 400 mL", 399),
        ("Toothpaste 100 mL", 249), ("Toothbrush Medium", 149),
        ("Shower Gel 250 mL", 279), ("Body Lotion 200 mL", 349),
        ("Cotton Buds 200 Pack", 139), ("Petroleum Jelly 100 mL", 179),
    ]),
    ("HOM", "Paper & Household", "Homecare Wholesale", [
        ("Toilet Tissue 4 Rolls", 299), ("Kitchen Towels 2 Rolls", 249),
        ("Facial Tissues 100 Sheets", 149), ("Paper Napkins 100 Pack", 129),
        ("Bin Liners 30 L 20 Pack", 229), ("Freezer Bags 25 Pack", 149),
        ("Aluminium Foil 10 m", 199), ("Cling Film 30 m", 179),
        ("Washing-Up Sponges 5 Pack", 129), ("Microfibre Cloths 3 Pack", 249),
    ]),
    ("STA", "Stationery", "Town Stationery Supply", [
        ("A5 Ruled Notebook 80 Pages", 149), ("A4 Ruled Notebook 160 Pages", 249),
        ("Blue Ballpoint Pens 5 Pack", 129), ("Black Ballpoint Pens 5 Pack", 129),
        ("HB Pencils 6 Pack", 149), ("White Eraser 2 Pack", 79),
        ("Pencil Sharpener", 69), ("Clear Ruler 30 cm", 99),
        ("Glue Stick 20 g", 139), ("Transparent Tape 18 mm", 99),
    ]),
    ("ESS", "Batteries & Essentials", "General Store Supply", [
        ("AA Alkaline Batteries 4 Pack", 349), ("AAA Alkaline Batteries 4 Pack", 349),
        ("9V Alkaline Battery", 299), ("LED Bulb 9 W Warm White", 249),
        ("LED Bulb 9 W Cool White", 249), ("Utility Candles 6 Pack", 179),
        ("Safety Matches 10 Boxes", 99), ("Cotton Shopping Bag", 199),
        ("Shoe Polish Black 50 mL", 179), ("Shoe Polish Brown 50 mL", 179),
    ]),
]


@dataclass(frozen=True)
class MovementSeed:
    movement_type: str
    quantity_change: int
    reason: str
    created_at: datetime


@dataclass(frozen=True)
class ProductSeed:
    fields: dict
    sku: str
    movements: tuple[MovementSeed, ...]
    archived_at: datetime | None


def build_seed(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Seed time must be timezone-aware.")
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    random = Random(20261102)
    result = []
    for prefix, category, supplier, items in CATALOG:
        for position, (name, price) in enumerate(items, start=1):
            index = len(result)
            fields = validated_fields({"name": name, "category": category, "unit_price_minor": price, "low_stock_threshold": random.choice((4, 6, 8, 10))})
            sku = clean_sku(f"{prefix}-{position:03}")
            span = timedelta(days=6 if prefix == "DRY" else 60)
            start = now - span - timedelta(hours=index % 24)
            movements = []
            balance = 0

            def add(kind, delta, fraction, reason):
                nonlocal balance
                integer(abs(delta), "quantityChange")
                if balance + delta < 0 or (kind != "OPENING" and delta == 0):
                    raise ValueError(f"Invalid stock trajectory for {sku}")
                if kind in {"OPENING", "RECEIVED"} and delta < 0 or kind == "ISSUED" and delta > 0:
                    raise ValueError(f"Invalid movement sign for {sku}")
                balance += delta
                movements.append(MovementSeed(kind, delta, clean_text(reason, "reason", 500), start + span * fraction))

            add("OPENING", random.randint(36, 84), 0, "Opening stock: physical count of shelf and storeroom packs.")
            add("RECEIVED", random.randint(24, 60), .22, f"Scheduled stock delivery from {supplier}.")
            add("ISSUED", -random.randint(12, 30), .40, "Retail counter sales: first trading-period tally.")
            add("RECEIVED", random.randint(18, 48), .62, f"Replenishment order received from {supplier}; packs checked on arrival.")
            add("ISSUED", -random.randint(8, 20), .78, "Retail counter sales: second trading-period tally.")
            if index % 3 == 0:
                adjustment = random.randint(1, 3) * (1 if index % 9 == 0 else -1)
                reason = "Physical count: extra sealed units found in a storeroom carton." if adjustment > 0 else "Damaged packaging removed after shelf inspection."
                add("ADJUSTMENT", adjustment, .90, reason)

            archived = (index + 1) % 20 == 0
            if archived or index % 13 == 0:
                target = 0
            elif index % 5 == 0:
                target = random.randint(1, fields["low_stock_threshold"])
            else:
                target = min(balance - 1, fields["low_stock_threshold"] + random.randint(8, 24))
            reason = "Final clearance of discontinued pack variant before archiving." if archived else "Last units sold; supplier restock pending." if target == 0 else "Retail counter sales: latest trading-period tally."
            add("ISSUED", target - balance, .98, reason)
            archived_at = movements[-1].created_at + timedelta(hours=1) if archived else None
            result.append(ProductSeed(fields, sku, tuple(movements), archived_at))
    if len({product.sku for product in result}) != len(result):
        raise ValueError("Seed catalog contains duplicate SKUs.")
    return result


def seed_database(database, now=None):
    """Insert only absent SKUs; preserve all existing product details/history.

    One immediate transaction protects the entire import, including duplicate
    checks. Failures roll back all new rows rather than leaving partial data.
    """
    catalog = build_seed(now)
    created = movement_count = skipped = 0
    with database.write() as session:
        existing = set(session.scalars(select(Product.sku).where(Product.sku.in_([row.sku for row in catalog]))))
        for row in catalog:
            if row.sku in existing:
                skipped += 1
                continue
            fields = {**row.fields, "category": canonical_category(session, row.fields["category"])}
            product = Product(
                sku=row.sku, **fields, created_at=row.movements[0].created_at,
                updated_at=row.archived_at or row.movements[-1].created_at,
                archived_at=row.archived_at,
            )
            session.add(product)
            session.flush()
            session.add_all([
                StockMovement(product_id=product.id, movement_type=movement.movement_type,
                              quantity_change=movement.quantity_change, reason=movement.reason,
                              created_at=movement.created_at)
                for movement in row.movements
            ])
            created += 1
            movement_count += len(row.movements)
    return {"created_products": created, "created_movements": movement_count, "skipped_existing_products": skipped}


def backup_database(database):
    directory = database.path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"inventory-before-seed-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.sqlite3"
    # SQLite's backup API gives a consistent snapshot even with a running app.
    source = sqlite3.connect(database.path)
    backup = sqlite3.connect(destination)
    try:
        source.backup(backup)
    finally:
        backup.close()
        source.close()
    return destination


def main():
    parser = argparse.ArgumentParser(description="Add 120 realistic products and linked historical movements without replacing existing data.")
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Show missing products without creating rows or a backup.")
    args = parser.parse_args()
    database = Database(args.database.resolve())
    try:
        database.check_schema()
        catalog = build_seed()
        with database.read() as session:
            existing = set(session.scalars(select(Product.sku)))
        missing = [row for row in catalog if row.sku not in existing]
        if args.dry_run:
            print(json.dumps({"database": str(database.path), "would_create_products": len(missing), "would_create_movements": sum(len(row.movements) for row in missing), "would_skip_products": len(catalog) - len(missing)}, indent=2))
            return
        backup = backup_database(database) if missing else None
        result = seed_database(database)
        print(json.dumps({"database": str(database.path), "backup": str(backup) if backup else None, **result, "dashboard": dashboard(database)}, indent=2))
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
