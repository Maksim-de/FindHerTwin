from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    description: str
    credits: int
    unlimited_days: int
    stars_amount: int
    usdt_amount: str


def load_products(payments_cfg: dict) -> dict[str, Product]:
    pack_cfg = payments_cfg.get("pack_15", {})
    unlimited_cfg = payments_cfg.get("unlimited", {})
    unlimited_days = int(payments_cfg.get("unlimited_days", 30))

    return {
        "pack_15": Product(
            id="pack_15",
            title="15 поисков",
            description="Пакет из 15 поисков (разовая покупка)",
            credits=int(pack_cfg.get("credits", 15)),
            unlimited_days=0,
            stars_amount=int(pack_cfg.get("stars", 250)),
            usdt_amount=str(pack_cfg.get("usdt", "3")),
        ),
        "unlimited": Product(
            id="unlimited",
            title=f"Безлимит на {unlimited_days} дн.",
            description=f"Неограниченные поиски на {unlimited_days} дней",
            credits=0,
            unlimited_days=unlimited_days,
            stars_amount=int(unlimited_cfg.get("stars", 400)),
            usdt_amount=str(unlimited_cfg.get("usdt", "5")),
        ),
    }
