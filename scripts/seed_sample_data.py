import os
import random
import sys
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "organic_hub.settings")

import django

django.setup()
from django.db import transaction
from django.utils import timezone

from core.models import (
    Address,
    CustomUser,
    Product,
    ProductVariant,
    Store,
    StoreVerificationRequest,
)

    SAMPLE_STORES = [
        {
            "user": {
            "full_name": "Lan Phạm",
                "email": "lan.pham@greenco.vn",
                "password": "LanPham#2024",
                "address": {
                    "street": "24 Nguyễn Đình Chiểu",
                    "ward": "Đa Kao",
                    "province": "TP. Hồ Chí Minh",
                "contact_person": "Lan Phạm",
                    "contact_phone": "0906 123 456",
                },
            },
        "store": {
            "store_name": "Green & Co. Organics",
            "store_description": "Specialized in leafy greens, cold-pressed herb blends, and curated same-day delivery produce boxes.",
        },
        },
        {
            "user": {
            "full_name": "Quang Lê",
                "email": "quang.le@mekongharvest.com",
                "password": "QuangLe#2024",
                "address": {
                    "street": "18 Lê Lợi",
                    "ward": "Ninh Kiều",
                    "province": "Cần Thơ",
                "contact_person": "Quang Lê",
                    "contact_phone": "0978 445 566",
                },
            },
        "store": {
            "store_name": "Mekong Harvest Collective",
            "store_description": "Collective of Mekong Delta growers offering ruby brown rice, melaleuca honey, and solar-dried tropical fruit.",
        },
        },
        {
            "user": {
            "full_name": "Mỹ Đặng",
                "email": "my.dang@highlandroots.vn",
                "password": "MyDang#2024",
                "address": {
                    "street": "42 Trần Hưng Đạo",
                    "ward": "Sơn Trà",
                    "province": "Đà Nẵng",
                "contact_person": "Mỹ Đặng",
                    "contact_phone": "0935 889 220",
                },
            },
        "store": {
            "store_name": "Highland Roots Market",
            "store_description": "Highland-sourced single-origin coffee, floral tisanes, and nutrient-dense seed blends roasted in small batches.",
        },
    },
]

SAMPLE_PRODUCTS = [
    {
        "name": "Cold-Pressed Kale Blend",
        "description": (
            "Organic kale, baby spinach, and Thai basil pressed within six hours of harvest. "
            "Ideal for detox juices, smoothie bases, or chilled wellness shots."
        ),
        "base_unit": "bottle",
        # Prices in GBP
        "price": "5.50",
        "stock": 0,
        "variants": [
            {
                "variant_name": "350ml – Morning Boost",
                "price": "3.50",
                "stock": 120,
            },
            {
                "variant_name": "500ml – Daily Cleanse",
                "price": "4.50",
                "stock": 80,
            },
            {
                "variant_name": "1L – Family Pack",
                "price": "7.50",
                "stock": 40,
            },
        ],
    },
]


def ensure_user(user_data):
    user, created = CustomUser.objects.get_or_create(
                    email=user_data["email"],
                    defaults={
                        "full_name": user_data["full_name"],
                        "email_verified": True,
                        "is_active": True,
                    },
                )
    if created:
                    user.set_password(user_data["password"])
                    user.save(update_fields=["password"])
                else:
                    updated = False
                    if user.full_name != user_data["full_name"]:
                        user.full_name = user_data["full_name"]
                        updated = True
                    if not user.email_verified:
                        user.email_verified = True
                        updated = True
                    if updated:
                        user.save()
    return user, created


def ensure_store(user, address_data, store_data):
                address, _ = Address.objects.get_or_create(
                    user=user,
                    street=address_data["street"],
                    ward=address_data["ward"],
                    province=address_data["province"],
                    defaults={
                        "country": "Vietnam",
                        "contact_person": address_data["contact_person"],
                        "contact_phone": address_data["contact_phone"],
                        "is_default": True,
                    },
                )

    store, created = Store.objects.get_or_create(
                    user=user,
                    store_name=store_data["store_name"],
                    defaults={
                        "store_description": store_data["store_description"],
                        "store_address": address,
                        "is_verified_status": "verified",
                    },
                )

    if not created:
        updates = {}
        if store.store_description != store_data["store_description"]:
            updates["store_description"] = store_data["store_description"]
        if store.store_address_id != address.address_id:
            updates["store_address"] = address
        if updates:
            Store.objects.filter(pk=store.pk).update(**updates)

                StoreVerificationRequest.objects.get_or_create(
                    store=store,
                    status="approved",
                    defaults={
                        "submitted_at": timezone.now() - timezone.timedelta(days=14),
                        "reviewed_at": timezone.now() - timezone.timedelta(days=12),
                        "admin_notes": "Seed data auto-approved for demo UI.",
                    },
                )
    return store, created


def ensure_product(store, product_data):
    product_defaults = {
        "description": product_data["description"],
        "price": Decimal(product_data["price"]),
        "base_unit": product_data["base_unit"],
        "stock": product_data.get("stock", 0),
        "has_variants": bool(product_data.get("variants")),
        "is_active": True,
    }
    product, created = Product.objects.get_or_create(
        store=store,
        name=product_data["name"],
        defaults=product_defaults,
    )

    if not created:
        updates = {}
        for field in ["description", "base_unit"]:
            if getattr(product, field) != product_data[field]:
                updates[field] = product_data[field]
        target_price = Decimal(product_data["price"])
        if product.price != target_price:
            updates["price"] = target_price
        desired_stock = product_data.get("stock", 0)
        if product.stock != desired_stock:
            updates["stock"] = desired_stock
        desired_has_variants = bool(product_data.get("variants"))
        if product.has_variants != desired_has_variants:
            updates["has_variants"] = desired_has_variants
        if updates:
            Product.objects.filter(pk=product.pk).update(**updates)

    variants_created = 0
    variants = product_data.get("variants", [])
    if variants:
        if not product.has_variants:
            product.has_variants = True
            product.save(update_fields=["has_variants"])

        for variant_data in variants:
            defaults = {
                "variant_description": variant_data.get("variant_description", ""),
                "price": Decimal(variant_data["price"]),
                "stock": variant_data["stock"],
                "is_active": True,
            }

            _, variant_created = ProductVariant.objects.update_or_create(
                product=product,
                variant_name=variant_data["variant_name"],
                defaults=defaults,
            )
            if variant_created:
                variants_created += 1
    return product, created, variants_created


def seed_products():
    stores = list(Store.objects.all())
    if not stores:
        print("No stores available. Skipping product seeding.")
        return 0, 0

    products_created = 0
    variants_created = 0

    for product_data in SAMPLE_PRODUCTS:
        store = random.choice(stores)
        product, product_created, variant_count = ensure_product(store, product_data)
        if product_created:
            products_created += 1
        variants_created += variant_count

    return products_created, variants_created


def seed():
    created_users = 0
    created_stores = 0

    with transaction.atomic():
        for entry in SAMPLE_STORES:
            user_data = entry["user"]
            store_data = entry["store"]

            user, user_created = ensure_user(user_data)
            if user_created:
                created_users += 1

            store, store_created = ensure_store(user, user_data["address"], store_data)
            if store_created:
                created_stores += 1

        products_created, variants_created = seed_products()

    print(
        f"Done. Users created: {created_users}, stores created: {created_stores}, "
        f"products created: {products_created}, variants created: {variants_created}"
            )


if __name__ == "__main__":
    seed()