""" Bunq api class """

import asyncio
import json
import socket
import uuid
from base64 import b64encode
from typing import Any, Awaitable, Callable, Optional

from aiohttp import ClientError, ClientSession, hdrs
from Cryptodome.PublicKey import RSA
from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey.RSA import RsaKey
from Cryptodome.Signature import PKCS1_v1_5

from .const import ENVIRONMENT_URLS, LOGGER, BunqApiEnvironment
from .exceptions import (
    BunqApiConnectionError,
    BunqApiConnectionTimeoutError,
    BunqApiError,
    BunqApiRateLimitError,
)
from .models import BunqStatus

MONETARY_ACCOUNT_TYPES = [
    "MonetaryAccountBank",
    "MonetaryAccountJoint",
    "MonetaryAccountLight",
    "MonetaryAccountSavings",
    "MonetaryAccountExternal",
]

# Substrings bunq returns (inside a 400 response) when the cached session is no
# longer accepted because the source IP no longer matches the device-server
# registration. This happens when the WAN IP changes while dynamic IP mode is
# disabled. Rebuilding the context re-registers a device-server from the current
# IP and recovers automatically, so we treat it like an expired session (401).
CONTEXT_INVALID_MESSAGES = (
    "User credentials are incorrect",
    "Incorrect API key or IP address",
)


def is_context_invalid_error(error: BunqApiError) -> bool:
    """Return True when the error means our session/context must be rebuilt.

    bunq returns 401 when the session token has expired, and 400 with an
    "Incorrect API key or IP address" message when the source IP no longer
    matches the device-server registration (e.g. the WAN IP changed) or the
    API key itself is no longer accepted. The IP case is recoverable by
    re-establishing the context; a credential that is rejected even after a
    fresh registration needs the user to re-authenticate.
    """
    status = error.args[0]
    if status == 401:
        return True
    if status == 400 and len(error.args) > 1 and isinstance(error.args[1], dict):
        for item in error.args[1].get("Error", []):
            description = item.get("error_description", "")
            if any(msg in description for msg in CONTEXT_INVALID_MESSAGES):
                return True
    return False


class BunqApi:
    """main api class"""

    _close_session: bool = False

    def __init__(
        self,
        *,
        environment: BunqApiEnvironment,
        token: str,
        request_timeout: int = 8,
        session: Optional[ClientSession] = None,
        token_refresh_method: Optional[Callable[[], Awaitable[str]]] = None,
        allow_dynamic_ip: bool = False,
    ) -> None:
        """Initialize connection with the Bunq API."""
        self.keys = None
        self._api_url = ENVIRONMENT_URLS[environment]["api_url"]
        self.status = BunqStatus()
        self._session = session
        self.request_timeout = request_timeout
        self.token = token
        self.allow_dynamic_ip = allow_dynamic_ip
        self.token_refresh_method = token_refresh_method

    async def close(self) -> None:
        """Close open client session."""
        if self._session and self._close_session:
            await self._session.close()
            LOGGER.debug("Session closed")

    async def _request(self, method, uri, **kwargs) -> Any:
        """Make a request."""
        if self.token_refresh_method is not None:
            self.token = await self.token_refresh_method()
            LOGGER.debug("Token refresh method called")

        url = self._api_url + uri
        headers = dict(kwargs.pop("headers", {}))
        token = kwargs.pop("token", None)
        signature = kwargs.pop("signature", "")

        LOGGER.debug("Executing %s API request to %s", method, url)

        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = "HomeAssistant"
        headers["X-Bunq-Language"] = "en_US"
        headers["X-Bunq-Region"] = "nl_NL"
        headers["X-Bunq-Geolocation"] = "0 0 0 0 000"
        headers["X-Bunq-Client-Signature"] = signature
        if token is not None:
            headers["X-Bunq-Client-Authentication"] = token
        headers["X-Bunq-Client-Request-Id"] = str(uuid.uuid4())

        if self._session is None:
            self._session = ClientSession()
            LOGGER.debug("New session created")
            self._close_session = True

        try:
            async with asyncio.timeout(self.request_timeout):
                response = await self._session.request(
                    method,
                    url,
                    **kwargs,
                    headers=headers,
                )
        except asyncio.TimeoutError as exception:
            raise BunqApiConnectionTimeoutError(
                "Timeout occurred while connecting to the Bunq API"
            ) from exception
        except (ClientError, socket.gaierror) as exception:
            raise BunqApiConnectionError(
                "Error occurred while communicating with the Bunq API"
            ) from exception

        content_type = response.headers.get("Content-Type", "")
        # Error handling
        if (response.status // 100) in [4, 5]:
            contents = await response.read()
            response.close()
            LOGGER.debug("Error response (status %d): %s", response.status, contents)
            if response.status == 429:
                raise BunqApiRateLimitError(
                    "Rate limit error has occurred with the Bunq API"
                )

            if content_type == "application/json":
                raise BunqApiError(response.status, json.loads(contents.decode("utf8")))
            raise BunqApiError(response.status, {"message": contents.decode("utf8")})

        # Handle empty response
        if response.status == 204:
            LOGGER.warning(
                "Request to %s resulted in status 204. Your dataset could be out of date",
                url,
            )
            return {"Response": []}

        if "application/json" in content_type:
            return await response.json()
        return await response.text()

    async def update(self) -> BunqStatus:
        """update data from bunq"""
        await self._setup_context()

        await self._update_accounts()

        for account in self.status.accounts:
            if account.get("_account_type") == "MonetaryAccountExternal":
                # bunq's public API exposes balance but not transaction history
                # for open-banking (PSD2) accounts. The payment endpoint returns
                # an empty list and all other known endpoints 404.
                LOGGER.debug(
                    "Skipping transaction fetch for external account %s (not available via public API)",
                    account["id"],
                )
                self.status.update_account_transactions(account["id"], [])
                continue
            try:
                await self.update_account_transactions(account["id"])
            except BunqApiError as error:
                account_type = account.get("_account_type", "unknown")
                LOGGER.warning(
                    "Could not fetch transactions for account %s (type: %s): %s",
                    account["id"],
                    account_type,
                    error,
                )
                self.status.update_account_transactions(account["id"], [])

        await self._update_cards()

        LOGGER.info("Status updated")
        return self.status

    def _get_user_id(self, data):
        for value in data["Response"]:
            if "UserApiKey" in value:
                return value["UserApiKey"]["id"]

    def _get_token(self, data):
        for value in data["Response"]:
            if "Token" in value:
                return value["Token"]["token"]

    def _generate_signature(self, string_to_sign: str, keys: RsaKey) -> str:
        LOGGER.debug("signing %s", string_to_sign)
        bytes_to_sign = string_to_sign.encode()
        signer = PKCS1_v1_5.new(keys)
        digest = SHA256.new()
        digest.update(bytes_to_sign)
        sign = signer.sign(digest)
        return b64encode(sign).decode("utf-8")

    async def _refresh_context(self):
        """Discard the cached session and rebuild it from the current IP."""
        LOGGER.info(
            "Re-establishing bunq context (session expired or source IP changed)"
        )
        self.status.update_user(None, None)
        await self._setup_context()

    async def _update_accounts(self):
        try:
            LOGGER.debug("Try to update accounts")
            await self._update_accounts_no_retry()
        except BunqApiError as error:
            LOGGER.debug("Received error %s", str(error))
            if is_context_invalid_error(error):
                LOGGER.debug("Retry to update accounts")
                await self._refresh_context()
                await self._update_accounts_no_retry()
            else:
                raise

    async def _update_accounts_no_retry(self):
        data = await self._fetch_monetary_accounts()
        LOGGER.debug("get_active_accounts response: %s", data)
        accounts = []
        for value in data["Response"]:
            for account_type in [
                key for key in value if key in MONETARY_ACCOUNT_TYPES
            ]:
                item = value[account_type]
                if "status" in item and item["status"] == "ACTIVE":
                    item["_account_type"] = account_type
                    if account_type == "MonetaryAccountExternal":
                        # bunq always returns balance=0.00 for external accounts.
                        # The real balance lives in open_banking_account.balance_booked.
                        oba = (
                            item.get("open_banking_account", {})
                            .get("OpenBankingAccount", {})
                        )
                        booked = oba.get("balance_booked")
                        if booked:
                            LOGGER.debug(
                                "External account %s: using balance_booked %s (was %s)",
                                item.get("id"),
                                booked,
                                item.get("balance"),
                            )
                            item["balance"] = booked
                    accounts.append(item)
        self.status.update_accounts(accounts)

    async def _update_cards(self):
        """update card data from bunq"""
        try:
            LOGGER.debug("Try to update cards")
            await self._update_cards_no_retry()
        except BunqApiError as error:
            LOGGER.debug("Received error %s", str(error))
            if is_context_invalid_error(error):
                LOGGER.debug("Retry to update cards")
                await self._refresh_context()
                await self._update_cards_no_retry()
            else:
                raise

    async def _update_cards_no_retry(self):
        data = await self._fetch_cards()
        LOGGER.debug("get cards response: %s", data)
        cards = []
        for value in data["Response"]:
            for card_type in [
                key for key in value if key in ["CardDebit", "CardCredit"]
            ]:
                item = value[card_type]
                if "status" in item and item["status"] == "ACTIVE":
                    cards.append(item)
        self.status.update_cards(cards)

    async def update_account_transactions(self, account_id):
        """Get transactions of an account."""
        data = await self._fetch_monetary_account_transactions(account_id)
        LOGGER.debug("get_account_transactions response: %s", data)
        transactions = []
        for value in data["Response"]:
            if "Payment" in value:
                item = value["Payment"]
                transactions.append(item)
        self.status.update_account_transactions(account_id, transactions)

    async def _fetch_monetary_account_transactions(self, account_id):
        return await self._request(
            hdrs.METH_GET,
            f"/v1/user/{self.status.user_id}/monetary-account/{account_id}/payment",
            token=self.status.session_token,
        )

    async def _fetch_monetary_accounts(self):
        return await self._request(
            hdrs.METH_GET,
            f"/v1/user/{self.status.user_id}/monetary-account?count=25",
            token=self.status.session_token,
        )

    async def _fetch_cards(self):
        return await self._request(
            hdrs.METH_GET,
            f"/v1/user/{self.status.user_id}/card",
            token=self.status.session_token,
        )

    async def link_account_to_card(self, card_id, account_id):
        """Link an account to a card."""

        card = self.status.get_card(card_id)
        if card is None:
            raise BunqApiError(f"card {card_id} not found")

        pins = card["pin_code_assignment"]
        for pin in pins:
            del pin["id"]
            del pin["created"]
            del pin["updated"]
            del pin["status"]
            if pin["type"] == "PRIMARY":
                pin["monetary_account_id"] = int(account_id)

        body = {"pin_code_assignment": pins}
        str_body = json.dumps(body)
        signature = self._generate_signature(str_body, self.keys)
        result = await self._request(
            hdrs.METH_PUT,
            f"/v1/user/{self.status.user_id}/card/{card_id}",
            token=self.status.session_token,
            signature=signature,
            data=str_body,
        )
        LOGGER.debug("link account response: %s", result)

        return result

    async def transfer(self, from_account_id, to_account_id, amount, message):
        """Transfer funds to one of your own accounts."""

        to_account = self.status.get_account(to_account_id)
        if to_account is None:
            raise BunqApiError(f"target account {to_account_id} not found")

        if "alias" not in to_account or len(to_account["alias"]) == 0:
            raise BunqApiError(f"no alias found for account {to_account_id}")
        alias = to_account["alias"][0]

        if "currency" not in to_account:
            raise BunqApiError(f"currency not found for account {to_account_id}")

        body = {
            "amount": {"value": str(amount), "currency": to_account["currency"]},
            "counterparty_alias": alias,
            "description": message,
        }
        str_body = json.dumps(body)
        signature = self._generate_signature(str_body, self.keys)
        result = await self._request(
            hdrs.METH_POST,
            f"/v1/user/{self.status.user_id}/monetary-account/{from_account_id}/payment",
            token=self.status.session_token,
            signature=signature,
            data=str_body,
        )
        LOGGER.debug("transfer response: %s", result)
        return result

    async def _setup_context(self):
        if self.status.user_id is not None and self.status.session_token is not None:
            LOGGER.debug("context already available")
            return
        self.keys = RSA.generate(2048)
        public_key_client = (
            self.keys.publickey()
            .export_key(format="PEM", passphrase=None, pkcs=8)
            .decode("utf-8")
        )

        installation = await self._request(
            hdrs.METH_POST,
            "/v1/installation",
            json={"client_public_key": public_key_client},
        )
        LOGGER.debug("installation response received")
        installation_token = self._get_token(installation)

        body = {
            "description": "Home Assistant",
            "secret": self.token,
        }
        if self.allow_dynamic_ip:
            body["permitted_ips"] = ["*"]
            LOGGER.info("Registering device server with wildcard permitted_ips (dynamic IP mode enabled)")
        await self._request(
            hdrs.METH_POST, "/v1/device-server", token=installation_token, json=body
        )
        LOGGER.debug("device-server response received")

        body = {"secret": self.token}
        str_body = json.dumps(body)
        signature = self._generate_signature(str_body, self.keys)
        session_server = await self._request(
            hdrs.METH_POST,
            "/v1/session-server",
            token=installation_token,
            signature=signature,
            data=str_body,
        )

        user_id = self._get_user_id(session_server)
        session_token = self._get_token(session_server)
        self.status.update_user(str(user_id), str(session_token))
        LOGGER.debug("context updated")
