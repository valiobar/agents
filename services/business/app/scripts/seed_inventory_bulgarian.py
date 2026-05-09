from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timezone
from decimal import Decimal

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings
from app.financial.repositories.financial_utils import decimal_to_bson
from app.inventory.repositories.inventory_item_repo import _build_search_text

CATEGORY_SMARTPHONES = "смартфони"
CATEGORY_ACCESSORIES = "аксесоари"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed 100 Bulgarian inventory items with stock balances in range 5..50. "
            "If company/user ids are omitted, the script auto-detects a default company."
        )
    )
    parser.add_argument("--user-id", default=None, help="Owner user_id for seeded records.")
    parser.add_argument("--company-id", default=None, help="Target company_id for seeded records.")
    parser.add_argument("--count", type=int, default=100, help="Number of items to create.")
    parser.add_argument("--min-stock", type=int, default=5, help="Minimum initial stock per item.")
    parser.add_argument("--max-stock", type=int, default=50, help="Maximum initial stock per item.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible stock values.")
    return parser.parse_args()


def _assert_object_id(label: str, value: str) -> None:
    if not ObjectId.is_valid(value):
        raise SystemExit(f"{label} must be a valid Mongo ObjectId. Got: {value}")


async def resolve_target(db: AsyncIOMotorDatabase, user_id: str | None, company_id: str | None) -> tuple[str, str]:
    if company_id is not None:
        _assert_object_id("--company-id", company_id)
        company = await db["companies"].find_one({"_id": ObjectId(company_id)})
        if company is None:
            raise SystemExit(f"Company not found for id={company_id}")
        resolved_user_id = str(company["user_id"])
        if user_id is not None and user_id != resolved_user_id:
            raise SystemExit(
                f"--user-id ({user_id}) does not match company owner ({resolved_user_id}) for company={company_id}"
            )
        return resolved_user_id, company_id

    if user_id is not None:
        _assert_object_id("--user-id", user_id)
        company = await db["companies"].find_one(
            {"user_id": user_id},
            sort=[("is_default", -1), ("created_at", -1)],
        )
        if company is None:
            raise SystemExit(f"No companies found for user_id={user_id}")
        return user_id, str(company["_id"])

    company = await db["companies"].find_one({}, sort=[("is_default", -1), ("created_at", -1)])
    if company is None:
        raise SystemExit("No companies found in DB. Create a company first.")
    return str(company["user_id"]), str(company["_id"])


async def ensure_default_location(db: AsyncIOMotorDatabase, user_id: str, company_id: str) -> str:
    location = await db["inventory_locations"].find_one(
        {"user_id": user_id, "company_id": company_id, "is_default": True}
    )
    if location is not None:
        return str(location["_id"])

    now = datetime.now(timezone.utc)
    result = await db["inventory_locations"].insert_one(
        {
            "user_id": user_id,
            "company_id": company_id,
            "name": "Основен склад",
            "description": "Автоматично създадена локация за тестови наличности.",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    return str(result.inserted_id)


def _item_specs() -> list[tuple[str, str, str, str]]:
    iphones = [
        "15 Pro 128GB",
        "15 Pro 256GB",
        "15 128GB",
        "15 Plus 256GB",
        "14 Pro 128GB",
        "14 128GB",
        "13 128GB",
        "13 mini 128GB",
        "SE 2022 64GB",
        "12 128GB",
        "11 64GB",
        "XS 64GB",
        "XR 64GB",
        "16 Pro 256GB",
        "16 128GB",
    ]
    samsung = [
        "Galaxy S24 256GB",
        "Galaxy S24 Ultra 512GB",
        "Galaxy S23 256GB",
        "Galaxy A55 128GB",
        "Galaxy A35 128GB",
        "Galaxy Z Fold5 512GB",
        "Galaxy Z Flip5 256GB",
        "Galaxy M54 128GB",
        "Galaxy A25 128GB",
        "Galaxy S22 128GB",
    ]
    xiaomi = [
        "Xiaomi 14 256GB",
        "Redmi Note 13 Pro 256GB",
        "Poco X6 Pro 256GB",
        "Redmi 13 128GB",
        "Xiaomi 13T 256GB",
        "Redmi Note 12 128GB",
        "Poco F6 256GB",
        "Xiaomi 14 Ultra 512GB",
    ]
    accessories = [
        ("Калъф за телефон MagSafe", "Защита за iPhone и други модели с магнитно захващане.", CATEGORY_ACCESSORIES, "бр."),
        ("Протектор за телефон 6.1 инча", "Закалено стъкло с висока прозрачност и защита от надраскване.", CATEGORY_ACCESSORIES, "бр."),
        ("Кабел USB-C 1м", "Бърз кабел за зареждане и пренос на данни за смартфон устройства.", CATEGORY_ACCESSORIES, "бр."),
        ("Зарядно 30W USB-C", "Компактно зарядно за телефон и смартфон с поддръжка на бързо зареждане.", CATEGORY_ACCESSORIES, "бр."),
        ("Безжични слушалки", "Слушалки с шумопотискане, удобни за ежедневна употреба.", "аудио", "бр."),
        ("Пауърбанк 20000mAh", "Външна батерия за зареждане на телефон и други мобилни устройства.", CATEGORY_ACCESSORIES, "бр."),
        ("Смарт часовник", "Умен часовник с мониторинг на активност и известия от смартфон.", "носими", "бр."),
        ("Bluetooth колонка", "Преносима колонка с чист звук и дълъг живот на батерията.", "аудио", "бр."),
        ("Стойка за телефон", "Регулируема стойка за бюро за смартфон и малък таблет.", CATEGORY_ACCESSORIES, "бр."),
        ("Авто зарядно USB-C", "Зарядно за автомобил с двойни портове за телефон устройства.", CATEGORY_ACCESSORIES, "бр."),
    ]
    specs: list[tuple[str, str, str, str]] = []

    for idx, model in enumerate(iphones):
        prefix = "Телефон iPhone" if idx % 2 == 0 else "Смартфон iPhone"
        title = f"{prefix} {model}"
        description = (
            "Оригинален iPhone с гаранция, подходящ за ежедневна работа, снимки и бизнес комуникация."
        )
        specs.append((title, description, CATEGORY_SMARTPHONES, "бр."))

    for model in samsung:
        specs.append(
            (
                f"Смартфон {model}",
                "Надежден Android смартфон с AMOLED дисплей и отлична батерия за целодневна работа.",
                CATEGORY_SMARTPHONES,
                "бр.",
            )
        )

    for model in xiaomi:
        specs.append(
            (
                f"Телефон {model}",
                "Достъпен смартфон с добър баланс между производителност, камера и цена.",
                CATEGORY_SMARTPHONES,
                "бр.",
            )
        )

    specs.extend(accessories)

    # Fill remaining rows with Bulgarian office/IT inventory.
    fillers = [
        ("Лаптоп бизнес клас", "Производителен лаптоп за офис работа, документи и видеосрещи.", "лаптопи", "бр."),
        ("Монитор 27 инча", "IPS монитор с висока резолюция за продуктивност и дизайн задачи.", "монитори", "бр."),
        ("Клавиатура механична", "Удобна клавиатура с българска подредба и стабилни суичове.", "периферия", "бр."),
        ("Мишка безжична", "Ергономична мишка за продължителна работа без умора.", "периферия", "бр."),
        ("Рутер Wi-Fi 6", "Стабилна безжична мрежа за офис с много едновременни устройства.", "мрежа", "бр."),
        ("SSD диск 1TB", "Бърз SSD за архив и работа с големи файлове.", "компоненти", "бр."),
        ("Принтер лазерен", "Лазерен принтер за бърз и икономичен печат на документи.", "офис техника", "бр."),
        ("Тонер касета", "Съвместима тонер касета с висок капацитет за ежедневен печат.", "консумативи", "бр."),
    ]
    while len(specs) < 100:
        base = fillers[len(specs) % len(fillers)]
        number = len(specs) + 1
        specs.append((f"{base[0]} модел {number}", base[1], base[2], base[3]))

    return specs[:100]


async def seed_inventory(
    db: AsyncIOMotorDatabase,
    *,
    user_id: str,
    company_id: str,
    count: int,
    min_stock: int,
    max_stock: int,
    seed: int,
) -> tuple[int, int, str]:
    if count <= 0:
        raise SystemExit("--count must be > 0")
    if min_stock <= 0 or max_stock <= 0 or min_stock > max_stock:
        raise SystemExit("Invalid stock bounds: require 0 < min-stock <= max-stock")

    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    location_id = await ensure_default_location(db, user_id, company_id)
    sku_prefix = now.strftime("BG%y%m%d%H%M%S")

    specs = _item_specs()
    docs: list[dict] = []
    movement_docs: list[dict] = []
    created = 0

    for index in range(count):
        title, description, category, unit = specs[index % len(specs)]
        sku = f"{sku_prefix}-{index + 1:03d}"
        barcode = f"380{seed:03d}{index + 1:06d}"
        aliases = [title.replace("Смартфон ", "").replace("Телефон ", ""), "мобилен телефон"]
        search_text = _build_search_text(title, sku, barcode, category, description, aliases)
        item_doc = {
            "user_id": user_id,
            "created_by_user_id": user_id,
            "updated_by_user_id": user_id,
            "company_id": company_id,
            "sku": sku,
            "name": title,
            "description": description,
            "category": category,
            "barcode": barcode,
            "aliases": aliases,
            "search_text": search_text,
            "unit": unit,
            "selling_price": Decimal(str(rng.randint(150, 3500))),
            "reorder_point": Decimal("5"),
            "target_stock_level": Decimal("30"),
            "supplier_partner_id": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        insert_result = await db["inventory_items"].insert_one(decimal_to_bson(item_doc))
        item_id = str(insert_result.inserted_id)
        stock_qty = Decimal(str(rng.randint(min_stock, max_stock)))
        movement_docs.append(
            {
                "user_id": user_id,
                "performed_by_user_id": user_id,
                "company_id": company_id,
                "item_id": item_id,
                "location_id": location_id,
                "movement_type": "receipt",
                "quantity_delta": stock_qty,
                "reason": "Начално зареждане за тестови данни",
                "source_type": "seed_bulgarian_inventory",
                "source_id": f"{sku_prefix}:{index + 1}",
                "source_line_id": "1",
                "occurred_at": now,
                "created_at": now,
            }
        )
        docs.append(item_doc)
        created += 1

    if movement_docs:
        await db["stock_movements"].insert_many(decimal_to_bson(movement_docs))

    return created, len(movement_docs), location_id


async def main() -> None:
    args = parse_args()
    client = AsyncIOMotorClient(settings.mongodb_url)
    try:
        db = client[settings.db_name]
        user_id, company_id = await resolve_target(db, args.user_id, args.company_id)
        created_items, created_movements, location_id = await seed_inventory(
            db,
            user_id=user_id,
            company_id=company_id,
            count=args.count,
            min_stock=args.min_stock,
            max_stock=args.max_stock,
            seed=args.seed,
        )
        print(f"user_id={user_id}")
        print(f"company_id={company_id}")
        print(f"location_id={location_id}")
        print(f"created_items={created_items}")
        print(f"created_stock_movements={created_movements}")
        print(f"stock_range={args.min_stock}..{args.max_stock}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
