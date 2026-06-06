from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from bot.analytics import EventLogger
from bot.payments.crypto_pay import CryptoPayClient
from bot.payments.products import Product
from bot.usage import UsageService

logger = logging.getLogger(__name__)

router = Router()

CALLBACK_BUY = "buy:"
CALLBACK_CRYPTO = "crypto:"
CALLBACK_STARS = "stars:"
CALLBACK_CHECK_CRYPTO = "check_crypto:"


def _buy_keyboard(
    products: dict[str, Product],
    crypto_enabled: bool,
    stars_enabled: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for product in products.values():
        row: list[InlineKeyboardButton] = []
        if stars_enabled:
            row.append(
                InlineKeyboardButton(
                    text=f"⭐ {product.title} — {product.stars_amount} Stars",
                    callback_data=f"{CALLBACK_STARS}{product.id}",
                )
            )
        if crypto_enabled:
            row.append(
                InlineKeyboardButton(
                    text=f"💎 {product.title} — {product.usdt_amount} USDT",
                    callback_data=f"{CALLBACK_CRYPTO}{product.id}",
                )
            )
        if row:
            rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_balance(summary: dict, free_daily_limit: int, limits_enabled: bool) -> str:
    if not limits_enabled:
        return "<b>Баланс</b>\n\nЛимиты отключены (тестовый режим)."

    lines = ["<b>Баланс</b>", ""]
    if summary["unlimited_active"]:
        until = summary["unlimited_until"]
        until_str = until.strftime("%d.%m.%Y %H:%M") if until else "—"
        lines.append(f"♾ Безлимит до: <b>{until_str}</b>")
    else:
        lines.append(f"🆓 Бесплатно сегодня: <b>{summary['daily_left']}</b> из {free_daily_limit}")
        lines.append(f"💳 Платные поиски: <b>{summary['credits']}</b>")
    lines.append("")
    lines.append("Тарифы: /buy")
    return "\n".join(lines)


@router.message(Command("balance"))
async def cmd_balance(message: Message, usage_service: UsageService) -> None:
    user_id = message.from_user.id if message.from_user else 0
    summary = await usage_service.get_summary(user_id)
    text = _format_balance(
        summary,
        usage_service.free_daily_limit,
        usage_service.limits_enabled,
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("buy"))
async def cmd_buy(
    message: Message,
    usage_service: UsageService,
    crypto_enabled: bool,
    stars_enabled: bool,
) -> None:
    products = usage_service.products
    text = (
        "<b>Тарифы</b>\n\n"
        f"🆓 <b>Бесплатно</b> — {usage_service.free_daily_limit} поиска в день\n"
        f"💎 <b>{products['pack_15'].title}</b> — ${products['pack_15'].usdt_amount} "
        f"({products['pack_15'].stars_amount} Stars)\n"
        f"♾ <b>{products['unlimited'].title}</b> — ${products['unlimited'].usdt_amount} "
        f"({products['unlimited'].stars_amount} Stars)\n\n"
        "Выберите способ оплаты:"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_buy_keyboard(
            products,
            crypto_enabled=crypto_enabled,
            stars_enabled=stars_enabled,
        ),
    )


@router.callback_query(F.data.startswith(CALLBACK_STARS))
async def on_stars_buy(
    callback: CallbackQuery,
    usage_service: UsageService,
    stars_enabled: bool,
) -> None:
    if not stars_enabled:
        await callback.answer("Оплата Stars отключена", show_alert=True)
        return
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    product_id = callback.data.removeprefix(CALLBACK_STARS)
    product = usage_service.get_product(product_id)
    user_id = callback.from_user.id
    payload = f"{product_id}:{user_id}"

    await callback.message.answer_invoice(
        title=product.title,
        description=product.description,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=product.title, amount=product.stars_amount)],
        provider_token="",
    )
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_CRYPTO))
async def on_crypto_buy(
    callback: CallbackQuery,
    usage_service: UsageService,
    crypto_pay: CryptoPayClient,
    crypto_enabled: bool,
) -> None:
    if not crypto_enabled:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    product_id = callback.data.removeprefix(CALLBACK_CRYPTO)
    product = usage_service.get_product(product_id)
    user_id = callback.from_user.id

    try:
        invoice = await crypto_pay.create_invoice(
            amount=product.usdt_amount,
            description=product.description,
            payload={"user_id": user_id, "product": product_id},
        )
    except Exception as exc:
        logger.exception("Crypto invoice error: %s", exc)
        await callback.answer("Не удалось создать счёт", show_alert=True)
        return

    await usage_service.create_payment(
        user_id=user_id,
        provider="crypto",
        product=product_id,
        external_id=str(invoice.invoice_id),
        amount=f"{product.usdt_amount} USDT",
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить в CryptoBot", url=invoice.pay_url)],
            [
                InlineKeyboardButton(
                    text="Проверить оплату",
                    callback_data=f"{CALLBACK_CHECK_CRYPTO}{invoice.invoice_id}",
                )
            ],
        ]
    )
    await callback.message.answer(
        f"<b>{product.title}</b>\n"
        f"Сумма: <b>{product.usdt_amount} USDT</b>\n\n"
        "Нажмите «Оплатить», затем «Проверить оплату».",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_CHECK_CRYPTO))
async def on_check_crypto(
    callback: CallbackQuery,
    usage_service: UsageService,
    crypto_pay: CryptoPayClient,
    analytics: EventLogger | None = None,
) -> None:
    if not callback.message or not callback.data:
        await callback.answer()
        return

    invoice_id = int(callback.data.removeprefix(CALLBACK_CHECK_CRYPTO))
    try:
        invoice = await crypto_pay.get_invoice(invoice_id)
    except Exception as exc:
        logger.exception("Crypto check error: %s", exc)
        await callback.answer("Ошибка проверки", show_alert=True)
        return

    if invoice.status != "paid":
        await callback.answer("Оплата ещё не поступила", show_alert=True)
        return

    result = await usage_service.complete_payment(str(invoice_id))
    if result is None:
        await callback.answer("Уже начислено", show_alert=True)
        return

    user_id, product_id = result
    if callback.from_user and callback.from_user.id != user_id:
        await callback.answer("Это не ваш платёж", show_alert=True)
        return

    msg = await usage_service.grant_product(user_id, product_id)
    if analytics:
        await analytics.log(
            user_id, "payment_success", provider="crypto", product=product_id
        )
    await callback.message.answer(f"✅ Оплата получена!\n{msg}")
    await callback.answer("Готово!")


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(
    message: Message,
    usage_service: UsageService,
    analytics: EventLogger | None = None,
) -> None:
    payment = message.successful_payment
    if not payment or not message.from_user:
        return

    payload = payment.invoice_payload or ""
    parts = payload.split(":", 1)
    if len(parts) != 2:
        logger.warning("Bad stars payload: %s", payload)
        await message.answer("Оплата получена, но не удалось начислить. Напишите в поддержку.")
        return

    product_id, user_id_str = parts
    user_id = int(user_id_str)
    if user_id != message.from_user.id:
        logger.warning("Stars user mismatch: %s vs %s", user_id, message.from_user.id)
        await message.answer("Ошибка начисления. Напишите в поддержку.")
        return

    external_id = payment.telegram_payment_charge_id
    await usage_service.create_payment(
        user_id=user_id,
        provider="stars",
        product=product_id,
        external_id=external_id,
        amount=f"{payment.total_amount} XTR",
    )
    result = await usage_service.complete_payment(external_id)
    if result is None:
        await message.answer("Платёж уже был обработан ранее.")
        return

    msg = await usage_service.grant_product(user_id, product_id)
    if analytics:
        await analytics.log(
            user_id, "payment_success", provider="stars", product=product_id
        )
    await message.answer(f"✅ Оплата получена!\n{msg}")
