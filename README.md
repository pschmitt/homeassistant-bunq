# bunq for Home Assistant

[![Open this integration in Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=pschmitt&repository=homeassistant-bunq&category=integration)

Home Assistant integration for bunq bank accounts. This is a fork of
[ben8p/home-assistant-bunq-balance-sensors](https://github.com/ben8p/home-assistant-bunq-balance-sensors).

## Features

- **External accounts:** Supports `MonetaryAccountExternal` via bunq Open Banking.
- **Device grouping:** Groups account entities under one bunq device.
- **Transaction polling:** Handles transaction fetch failures for external accounts.

## Install

Use the badge to add the repository as a custom integration in Home Assistant
Marketplace (Home Assistant 2026.11 or later), then install it and restart Home
Assistant. On older versions, add this repository in HACS as a custom
integration. Go to **Settings → Devices & services → Add integration**, select
**bunq**, and complete the OAuth2 setup.
