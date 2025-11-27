from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Optional, Dict

from web3 import Web3
from web3.exceptions import ContractLogicError

from app.core.config import settings

# ABI מינימלי ל-ERC20: balanceOf + decimals
SLH_ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


@lru_cache
def get_web3() -> Web3:
    """
    Web3 מחובר ל-BNB Smart Chain.
    אם לא הוגדר BSC_RPC_URL בסביבה, נשתמש ב-node הציבורי.
    """
    rpc_url = settings.BSC_RPC_URL or "https://bsc-dataseed.binance.org/"
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
    return w3


@lru_cache
def get_slh_contract():
    """
    מחזיר אובייקט חוזה ל-SLH אם יש כתובת, אחרת None.
    """
    token_address = settings.SLH_TOKEN_ADDRESS
    if not token_address:
        return None

    w3 = get_web3()
    try:
        checksum = w3.to_checksum_address(token_address)
    except ValueError:
        # כתובת לא תקינה
        return None

    return w3.eth.contract(address=checksum, abi=SLH_ERC20_ABI)


def get_onchain_bnb_balance(address: str) -> Optional[Decimal]:
    """
    מחזיר יתרת BNB לכתובת הנתונה (כ-Decimal),
    או None אם יש בעיה (RPC down, כתובת לא תקינה וכו').
    """
    if not address:
        return None

    w3 = get_web3()
    try:
        checksum = w3.to_checksum_address(address)
    except ValueError:
        return None

    try:
        wei_balance = w3.eth.get_balance(checksum)
    except Exception:
        return None

    # 1 BNB = 10**18 wei
    return Decimal(wei_balance) / Decimal(10**18)


def get_onchain_slh_balance(address: str) -> Optional[Decimal]:
    """
    מחזיר יתרת SLH לכתובת הנתונה (כ-Decimal),
    לפי ה-decimals של הטוקן מהחוזה עצמו.
    """
    if not address:
        return None

    contract = get_slh_contract()
    if contract is None:
        return None

    w3 = get_web3()
    try:
        checksum = w3.to_checksum_address(address)
    except ValueError:
        return None

    try:
        raw_balance = contract.functions.balanceOf(checksum).call()
        decimals = contract.functions.decimals().call()
    except (ContractLogicError, ValueError, Exception):
        return None

    factor = Decimal(10) ** Decimal(decimals)
    return Decimal(raw_balance) / factor


def get_onchain_balances(address: str) -> Dict[str, Optional[Decimal]]:
    """
    מחזיר מילון עם:
    {
        "bnb": Decimal | None,
        "slh": Decimal | None,
    }
    """
    bnb = get_onchain_bnb_balance(address)
    slh = get_onchain_slh_balance(address)
    return {"bnb": bnb, "slh": slh}
