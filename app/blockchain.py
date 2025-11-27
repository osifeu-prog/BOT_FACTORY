# app/blockchain.py
import logging
from decimal import Decimal
from typing import Optional, Dict

from web3 import Web3

from app.core.config import settings

logger = logging.getLogger(__name__)

_w3: Optional[Web3] = None
_slh_contract = None


def _get_w3() -> Optional[Web3]:
    """
    יוצר מחבר Web3 ל-BNB Chain (BSC) לפי BSC_RPC_URL.
    אם משהו נכשל – מחזיר None ולא מפיל את הבוט.
    """
    global _w3

    if _w3 is not None:
        return _w3

    if not settings.BSC_RPC_URL:
        logger.warning("BSC_RPC_URL is not configured – on-chain balances disabled")
        return None

    try:
        w3 = Web3(Web3.HTTPProvider(settings.BSC_RPC_URL))
        if not w3.is_connected():
            logger.warning(
                "Could not connect to BSC RPC at %s", settings.BSC_RPC_URL
            )
            return None

        _w3 = w3
        logger.info("Connected to BSC RPC: %s", settings.BSC_RPC_URL)
        return _w3
    except Exception as e:
        logger.exception("Error creating Web3 provider: %s", e)
        return None


def _get_slh_contract(w3: Web3):
    """
    יוצר חוזה SLH מינימלי (balanceOf בלבד).
    """
    global _slh_contract

    if _slh_contract is not None:
        return _slh_contract

    if not settings.SLH_TOKEN_ADDRESS:
        logger.warning("SLH_TOKEN_ADDRESS is not set – token balance disabled")
        return None

    abi = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        }
    ]

    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.SLH_TOKEN_ADDRESS),
            abi=abi,
        )
        _slh_contract = contract
        return _slh_contract
    except Exception as e:
        logger.exception("Error creating SLH token contract: %s", e)
        return None


def get_onchain_balances(address: str) -> Dict[str, Optional[Decimal]]:
    """
    מחזיר dict:
    {
      "bnb": Decimal(...) או None,
      "slh": Decimal(...) או None
    }

    אם יש בעיה ב-RPC / כתובת / טוקן – נחזיר None במקום ערך,
    אבל *לא* נפוצץ את המערכת.
    """
    w3 = _get_w3()
    if w3 is None:
        return {"bnb": None, "slh": None}

    try:
        checksum = w3.to_checksum_address(address)
    except Exception:
        logger.warning("Invalid BSC address for on-chain lookup: %s", address)
        return {"bnb": None, "slh": None}

    bnb_dec: Optional[Decimal] = None
    slh_dec: Optional[Decimal] = None

    # === BNB native balance ===
    try:
        raw_bnb = w3.eth.get_balance(checksum)
        bnb_dec = Decimal(raw_bnb) / Decimal(10**18)
    except Exception as e:
        logger.warning("Failed to fetch BNB balance: %s", e)

    # === SLH token balance ===
    try:
        contract = _get_slh_contract(w3)
        if contract is not None:
            raw_slh = contract.functions.balanceOf(checksum).call()
            decimals = int(settings.SLH_TOKEN_DECIMALS or 18)
            slh_dec = Decimal(raw_slh) / Decimal(10**decimals)
    except Exception as e:
        logger.warning("Failed to fetch SLH token balance: %s", e)

    return {"bnb": bnb_dec, "slh": slh_dec}
