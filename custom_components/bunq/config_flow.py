"""Config flow for Bunq."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import \
    AbstractOAuth2FlowHandler

from .bunq_api import BunqApi
from .const import CONF_ALLOW_DYNAMIC_IP, DOMAIN, ENVIRONMENT, LOGGER


class BunqFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Bunq OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    # Dynamic IP choice carried from the reauth_confirm step through the OAuth
    # redirect round-trip into async_oauth_create_entry. None means "leave the
    # existing option untouched" (e.g. a fresh, non-reauth install).
    _reauth_allow_dynamic_ip: bool | None = None

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return BunqOptionsFlowHandler()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        LOGGER.debug("async_step_reauth: reauth required, moving to confirm step")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth and let the user choose the dynamic IP setting."""
        LOGGER.debug("async_step_reauth_confirm: user_input=%s", user_input is not None)

        reauth_entry = self._get_reauth_entry()
        default_dynamic_ip = bool(
            reauth_entry.options.get(CONF_ALLOW_DYNAMIC_IP, False)
            if reauth_entry
            else False
        )

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_ALLOW_DYNAMIC_IP, default=default_dynamic_ip
                        ): bool,
                    }
                ),
            )

        self._reauth_allow_dynamic_ip = bool(
            user_input.get(CONF_ALLOW_DYNAMIC_IP, default_dynamic_ip)
        )
        LOGGER.debug(
            "async_step_reauth_confirm: confirmed, allow_dynamic_ip=%s, starting user step",
            self._reauth_allow_dynamic_ip,
        )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        LOGGER.debug("async_oauth_create_entry: received token data keys=%s", list(data.get("token", {}).keys()))

        token = data.get("token", {})
        if not token.get("access_token"):
            LOGGER.error("async_oauth_create_entry: access_token missing from token data")
            return self.async_abort(reason="oauth_error")

        LOGGER.debug("async_oauth_create_entry: creating BunqApi and calling update()")
        try:
            api = BunqApi(
                environment=ENVIRONMENT,
                token=token["access_token"],
                session=async_get_clientsession(self.hass),
                allow_dynamic_ip=bool(self._reauth_allow_dynamic_ip),
            )
            status = await api.update()
        except Exception as err:
            LOGGER.error("async_oauth_create_entry: BunqApi.update() failed: %s", err, exc_info=True)
            return self.async_abort(reason="oauth_error")

        LOGGER.debug(
            "async_oauth_create_entry: update() result: user_id=%s, session_token_present=%s",
            status.user_id,
            bool(status.session_token),
        )

        if not status.user_id or not status.session_token:
            LOGGER.error(
                "async_oauth_create_entry: aborting — user_id=%s, session_token_present=%s",
                status.user_id,
                bool(status.session_token),
            )
            return self.async_abort(reason="oauth_error")

        unique_id = status.user_id.lower()
        LOGGER.debug("async_oauth_create_entry: setting unique_id=%s", unique_id)

        # Reauth path: use _get_reauth_entry() — more reliable than async_set_unique_id
        # in a reauth-flow context, and avoids blocking async_step_creation with a long
        # await async_reload() that can cause a second OAuth code exchange attempt.
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            LOGGER.debug("async_oauth_create_entry: reauth flow, updating entry %s", reauth_entry.entry_id)
            if self._reauth_allow_dynamic_ip is not None:
                new_options = dict(reauth_entry.options)
                new_options[CONF_ALLOW_DYNAMIC_IP] = self._reauth_allow_dynamic_ip
                return self.async_update_and_abort(reauth_entry, data=data, options=new_options)
            return self.async_update_and_abort(reauth_entry, data=data)

        LOGGER.debug("async_oauth_create_entry: creating new config entry for user_id=%s", status.user_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=status.user_id, data=data)


class BunqOptionsFlowHandler(OptionsFlow):
    """Handle bunq options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage bunq options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALLOW_DYNAMIC_IP,
                        default=self.config_entry.options.get(
                            CONF_ALLOW_DYNAMIC_IP, False
                        ),
                    ): bool,
                }
            ),
        )
