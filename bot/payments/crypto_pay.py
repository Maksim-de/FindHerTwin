"""Клиент Crypto Pay API (@CryptoBot)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

API_BASE_MAINNET = "https://pay.crypt.bot/api"
API_BASE_TESTNET = "https://testnet-pay.crypt.bot/api"


@dataclass
class CryptoInvoice:
    invoice_id: int
    pay_url: str
    status: str


class CryptoPayClient:
    def __init__(self, api_token: str, *, testnet: bool = False) -> None:
        self.api_token = api_token.strip()
        self.testnet = testnet
        self.api_base = API_BASE_TESTNET if testnet else API_BASE_MAINNET
        self._session: aiohttp.ClientSession | None = None
        if self.enabled and testnet:
            logger.warning("Crypto Pay testnet: %s (@CryptoTestnetBot)", self.api_base)

    @property
    def enabled(self) -> bool:
        return bool(self.api_token)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Crypto-Pay-API-Token": self.api_token},
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        session = await self._get_session()
        url = f"{self.api_base}/{path}"
        async with session.request(method, url, **kwargs) as resp:
            data = await resp.json()
        if not data.get("ok"):
            error = data.get("error", "unknown error")
            raise RuntimeError(f"Crypto Pay API error: {error}")
        return data["result"]

    async def create_invoice(
        self,
        amount: str,
        description: str,
        payload: dict,
        asset: str = "USDT",
    ) -> CryptoInvoice:
        body = {
            "asset": asset,
            "amount": amount,
            "description": description,
            "payload": json.dumps(payload, separators=(",", ":")),
            "expires_in": 3600,
        }
        result = await self._request("POST", "createInvoice", json=body)
        return CryptoInvoice(
            invoice_id=int(result["invoice_id"]),
            pay_url=result.get("bot_invoice_url") or result.get("pay_url", ""),
            status=result.get("status", "active"),
        )

    async def get_invoice(self, invoice_id: int) -> CryptoInvoice:
        result = await self._request("GET", "getInvoices", params={"invoice_ids": str(invoice_id)})
        items = result.get("items") or []
        if not items:
            raise RuntimeError(f"Invoice {invoice_id} not found")
        item = items[0]
        return CryptoInvoice(
            invoice_id=int(item["invoice_id"]),
            pay_url=item.get("bot_invoice_url") or item.get("pay_url", ""),
            status=item.get("status", "active"),
        )
