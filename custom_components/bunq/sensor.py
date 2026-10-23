"""Support for bunq account balance."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bunq_balance_sensor import BunqBalanceSensor
from .bunq_card_sensor import BunqCardSensor
from .const import DOMAIN
from .coordinator import BunqDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a bunq sensor entry."""
    coordinator: BunqDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_accounts: set[str] = set()
    known_cards: set[str] = set()

    @callback
    def _add_missing() -> None:
        sensors = []
        for account in coordinator.bunq.status.accounts:
            key = str(account["id"])
            if key not in known_accounts:
                known_accounts.add(key)
                sensors.append(BunqBalanceSensor(coordinator, account))
        for card in coordinator.bunq.status.cards:
            key = str(card["id"])
            if key not in known_cards:
                known_cards.add(key)
                sensors.append(BunqCardSensor(coordinator, card))
        if sensors:
            async_add_entities(sensors)

    _add_missing()
    entry.async_on_unload(coordinator.async_add_listener(_add_missing))
