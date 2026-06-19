"""Event platform for bunq — fires on new bank transactions."""

from __future__ import annotations

import logging

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BunqDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the bunq last-transaction event entity."""
    coordinator: BunqDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([BunqLastTransactionEvent(coordinator)])


class BunqLastTransactionEvent(CoordinatorEntity[BunqDataUpdateCoordinator], EventEntity):
    """Event entity that fires when a new bunq payment is detected.

    Watches all monetary accounts and fires on the most recently created
    payment across all of them.
    """

    _attr_has_entity_name = True
    _attr_event_types = ["transaction"]
    _attr_name = "Last transaction"
    _attr_icon = "mdi:bank-transfer"

    def __init__(self, coordinator: BunqDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}:last_transaction"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="bunq",
            model="bunq",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._last_tx_id: int | None = None
        self._initialized = False

    @callback
    def _handle_coordinator_update(self) -> None:
        try:
            account_transactions = self.coordinator.bunq.status.account_transactions
        except AttributeError:
            super()._handle_coordinator_update()
            return

        latest = _latest_transaction(account_transactions)
        if latest is None:
            super()._handle_coordinator_update()
            return

        tx_id = latest.get("id")

        if not self._initialized:
            self._last_tx_id = tx_id
            self._initialized = True
        elif tx_id is not None and tx_id != self._last_tx_id:
            self._last_tx_id = tx_id
            amount_obj = latest.get("amount") or {}
            self._trigger_event(
                "transaction",
                {
                    "transaction_id": tx_id,
                    "created": latest.get("created"),
                    "type": latest.get("type"),
                    "amount": amount_obj.get("value"),
                    "currency": amount_obj.get("currency"),
                    "description": latest.get("description"),
                    "counterparty": (latest.get("counterparty_alias") or {}).get(
                        "display_name"
                    ),
                },
            )
            return  # _trigger_event already calls async_write_ha_state

        super()._handle_coordinator_update()


def _latest_transaction(account_transactions: dict) -> dict | None:
    """Return the most recently created payment across all accounts."""
    best: dict | None = None
    best_created = ""
    for payments in account_transactions.values():
        if not payments:
            continue
        # bunq API returns payments newest-first; first entry is the latest.
        tx = payments[0]
        created = tx.get("created") or ""
        if created > best_created:
            best_created = created
            best = tx
    return best
