from __future__ import annotations

from decimal import Decimal
from typing import Any

from web3 import Web3
from web3.middleware import geth_poa_middleware  # type: ignore

from app.core.config import settings


# --- Web3 bootstrap ---------------------------------------------------------


def get_web3() -> Web3:
    if not settings.BSC_RPC_URL:
        raise RuntimeError("BSC_RPC_URL is not configured")
    w3 = Web3(Web3.HTTPProvider(settings.BSC_RPC_URL))
    # BNB Smart Chain is POA-like – add middleware if needed
    if not w3.middleware_onion:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # type: ignore[arg-type]
    return w3


# --- Minimal ERC-20 ABI for SLH --------------------------------------------

# מספיק לנו ABI מינימלי – כל עוד החתימות נכונות, אין חובה לכלול את כל החוזה
MINIMAL_ERC20_ABI: list[dict[str, Any]] = [
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def get_slh_contract(w3: Web3):
    if not settings.SLH_TOKEN_ADDRESS:
        raise RuntimeError("SLH_TOKEN_ADDRESS is not configured")
    return w3.eth.contract(
        address=w3.to_checksum_address(settings.SLH_TOKEN_ADDRESS),
        abi=MINIMAL_ERC20_ABI,
    )


def get_slh_decimals(w3: Web3) -> int:
    """
    קורא את decimals מהחוזה עצמו.
    אם זה נכשל מסיבה כלשהי – נופל חזרה ל-SLH_TOKEN_DECIMALS מה-ENV.
    """
    contract = get_slh_contract(w3)
    try:
        return int(contract.functions.decimals().call())
    except Exception:
        if settings.SLH_TOKEN_DECIMALS:
            return int(settings.SLH_TOKEN_DECIMALS)
        # ברירת מחדל בטוחה
        return 18


# --- Community hot wallet helpers ------------------------------------------


def _get_community_wallet(w3: Web3):
    if not settings.COMMUNITY_WALLET_ADDRESS:
        raise RuntimeError("COMMUNITY_WALLET_ADDRESS is not configured")
    if not settings.COMMUNITY_WALLET_PRIVATE_KEY:
        raise RuntimeError("COMMUNITY_WALLET_PRIVATE_KEY is not configured")

    from_addr = w3.to_checksum_address(settings.COMMUNITY_WALLET_ADDRESS)
    pk = settings.COMMUNITY_WALLET_PRIVATE_KEY
    if not pk.startswith("0x"):
        raise RuntimeError("COMMUNITY_WALLET_PRIVATE_KEY must start with 0x")

    return from_addr, pk


def send_bnb_from_community(to_address: str, amount_bnb: Decimal) -> str:
    """
    שולח BNB מהארנק הקהילתי (hot wallet) לכתובת יעד.
    מחזיר hash של הטרנזקציה.
    """
    w3 = get_web3()
    from_addr, pk = _get_community_wallet(w3)

    to_addr = w3.to_checksum_address(to_address)
    value_wei = int(Decimal(amount_bnb) * Decimal(10**18))

    nonce = w3.eth.get_transaction_count(from_addr)

    tx = {
        "from": from_addr,
        "to": to_addr,
        "value": value_wei,
        "nonce": nonce,
        "gasPrice": w3.eth.gas_price,
    }
    # הערכת gas דינמית
    gas_limit = w3.eth.estimate_gas(tx)
    tx["gas"] = gas_limit

    signed = w3.eth.account.sign_transaction(tx, private_key=pk)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()


def send_slh_from_community(to_address: str, amount_slh: Decimal) -> str:
    """
    שולח SLH (BEP-20) מהארנק הקהילתי לכתובת יעד.

    amount_slh – בכמות "אנושית" (למשל 10 = 10 SLH),
    לא בכפולה של 10**decimals.
    """
    w3 = get_web3()
    from_addr, pk = _get_community_wallet(w3)

    to_addr = w3.to_checksum_address(to_address)
    contract = get_slh_contract(w3)

    decimals = get_slh_decimals(w3)
    raw_amount = int(Decimal(amount_slh) * Decimal(10**decimals))

    nonce = w3.eth.get_transaction_count(from_addr)

    tx = contract.functions.transfer(to_addr, raw_amount).build_transaction(
        {
            "from": from_addr,
            "nonce": nonce,
            "gasPrice": w3.eth.gas_price,
        }
    )
    # הערכת gas על בסיס החוזה
    gas_limit = w3.eth.estimate_gas(tx)
    tx["gas"] = gas_limit

    signed = w3.eth.account.sign_transaction(tx, private_key=pk)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()
