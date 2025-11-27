from decimal import Decimal
import os

from web3 import Web3

from app.core.config import settings


def get_onchain_balances(address: str) -> dict:
    if not settings.BSC_RPC_URL or not settings.SLH_TOKEN_ADDRESS:
        return {}

    w3 = Web3(Web3.HTTPProvider(settings.BSC_RPC_URL))
    if not w3.is_connected():
        return {}

    checksum_addr = w3.to_checksum_address(address)
    token_addr = w3.to_checksum_address(settings.SLH_TOKEN_ADDRESS)

    bnb_balance_wei = w3.eth.get_balance(checksum_addr)
    bnb = Decimal(bnb_balance_wei) / Decimal(10**18)

    erc20_abi = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        }
    ]

    token = w3.eth.contract(address=token_addr, abi=erc20_abi)
    raw_slh = token.functions.balanceOf(checksum_addr).call()

    decimals = settings.SLH_TOKEN_DECIMALS or 18
    slh = Decimal(raw_slh) / Decimal(10**decimals)

    return {"bnb": bnb, "slh": slh}
