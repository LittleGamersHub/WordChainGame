"""Read-only client for Polymarket public APIs.

Strictly read-only. No authentication. No order placement. No wallet signing.
The client only issues HTTP GETs against Polymarket's public endpoints:

    Gamma API   (market metadata):  https://gamma-api.polymarket.com
    CLOB API    (book + prices):    https://clob.polymarket.com
    Data API    (on-chain trades):  https://data-api.polymarket.com

Schemas are controlled by Polymarket and may change; treat every field as
optional and fall back to None. Runs on the Python stdlib — no extra deps.

Usage:
    reader = PolymarketReader()
    markets = reader.fetch_markets(limit=20, min_volume=50_000)
    for m in markets:
        trades = reader.fetch_trades(m["conditionId"], limit=500)
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
DATA_BASE = "https://data-api.polymarket.com"

DEFAULT_UA = "whale-bot-poc/0.1 (research; read-only)"


@dataclass
class ReaderConfig:
    gamma_base: str = GAMMA_BASE
    clob_base: str = CLOB_BASE
    data_base: str = DATA_BASE
    user_agent: str = DEFAULT_UA
    timeout: float = 15.0
    max_retries: int = 4
    backoff_seconds: float = 1.5


class PolymarketReader:
    def __init__(self, config: ReaderConfig | None = None) -> None:
        self.cfg = config or ReaderConfig()

    # ---- low-level GET ---------------------------------------------------

    def _get_json(self, url: str) -> Any:
        last_err: Exception | None = None
        for attempt in range(self.cfg.max_retries):
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.cfg.user_agent,
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                # Retry on 429 / 5xx only.
                if e.code == 429 or 500 <= e.code < 600:
                    last_err = e
                else:
                    raise
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
            time.sleep(self.cfg.backoff_seconds * (2 ** attempt))
        raise RuntimeError(f"GET failed after retries: {url}  ({last_err})")

    @staticmethod
    def _qs(params: dict[str, Any]) -> str:
        clean = {k: v for k, v in params.items() if v is not None}
        return urllib.parse.urlencode(clean, doseq=True)

    # ---- Gamma: market metadata -----------------------------------------

    def fetch_markets(
        self,
        limit: int = 100,
        active: bool | None = True,
        closed: bool | None = False,
        archived: bool | None = False,
        min_volume: float | None = None,
        order: str | None = "volumeNum",
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        """List markets from the Gamma API.

        Returned dicts include (when present): id, question, conditionId,
        clobTokenIds, outcomes, outcomePrices, volumeNum, liquidityNum, endDate.
        """
        qs = self._qs(
            {
                "limit": limit,
                "active": str(active).lower() if active is not None else None,
                "closed": str(closed).lower() if closed is not None else None,
                "archived": str(archived).lower() if archived is not None else None,
                "order": order,
                "ascending": "true" if ascending else "false",
            }
        )
        url = f"{self.cfg.gamma_base}/markets?{qs}"
        data = self._get_json(url)
        if not isinstance(data, list):
            return []
        if min_volume is not None:
            data = [m for m in data if _to_float(m.get("volumeNum")) >= min_volume]
        return data

    def fetch_market(self, condition_id: str) -> dict[str, Any] | None:
        url = f"{self.cfg.gamma_base}/markets?{self._qs({'condition_ids': condition_id})}"
        data = self._get_json(url)
        if isinstance(data, list) and data:
            return data[0]
        return None

    # ---- CLOB: live prices ----------------------------------------------

    def fetch_clob_market(self, condition_id: str) -> dict[str, Any] | None:
        """CLOB market metadata including token IDs and current best prices."""
        url = f"{self.cfg.clob_base}/markets/{condition_id}"
        try:
            return self._get_json(url)
        except RuntimeError:
            return None

    def fetch_midpoint(self, token_id: str) -> float | None:
        """Midpoint price for an outcome token (0..1)."""
        url = f"{self.cfg.clob_base}/midpoint?token_id={urllib.parse.quote(token_id)}"
        try:
            data = self._get_json(url)
        except RuntimeError:
            return None
        mid = data.get("mid") if isinstance(data, dict) else None
        return _to_float(mid)

    # ---- Data API: on-chain trades --------------------------------------

    def fetch_trades(
        self,
        market_condition_id: str | None = None,
        user: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Recent trades. Filter by market (conditionId) or wallet address.

        Returned dicts include (when present): proxyWallet, timestamp, side,
        price, size, outcome, outcomeIndex, asset, transactionHash.
        """
        qs = self._qs(
            {
                "market": market_condition_id,
                "user": user,
                "limit": limit,
                "offset": offset,
            }
        )
        url = f"{self.cfg.data_base}/trades?{qs}"
        data = self._get_json(url)
        return data if isinstance(data, list) else []

    def fetch_all_trades_for_market(
        self,
        market_condition_id: str,
        max_trades: int = 5_000,
        page_size: int = 500,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        offset = 0
        while len(out) < max_trades:
            page = self.fetch_trades(
                market_condition_id=market_condition_id,
                limit=page_size,
                offset=offset,
            )
            if not page:
                break
            out.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return out[:max_trades]


# ---- helpers -------------------------------------------------------------


def _to_float(x: Any) -> float:
    try:
        return float(x) if x is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
