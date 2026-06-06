# homeassistant-bunq

Home Assistant integration for bunq bank accounts.

Fork of [ben8p/home-assistant-bunq-balance-sensors](https://github.com/ben8p/home-assistant-bunq-balance-sensors) with:

- **External account support** (`MonetaryAccountExternal` via bunq Open Banking)
- **Device registry** — all entities are grouped under a single bunq device
- Graceful handling of transaction fetch failures for external accounts
