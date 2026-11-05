<p align="center">
  <a href="https://my.home-assistant.io/redirect/marketplace_repository/?owner=pschmitt&amp;repository=homeassistant-bunq&amp;category=integration"><img src="https://my.home-assistant.io/badges/marketplace_repository.svg" alt="Open this integration in Home Assistant Marketplace"></a>
</p>

<h1 align="center">bunq for Home Assistant</h1>

<p align="center">Read bunq account balances and transactions as Home Assistant sensors.</p>

This is a fork of [bunq Balance Sensors](https://github.com/ben8p/home-assistant-bunq-balance-sensors).

## Features

- **External accounts:** Include `MonetaryAccountExternal` balances through bunq Open Banking.
- **Device grouping:** Group account entities under one bunq device.
- **Transaction polling:** Keep account sensors available when transaction retrieval fails for an external account.

## Install

Use the Marketplace badge above on Home Assistant 2026.11 or later to add this
repository as a custom integration. On older versions, add it as a HACS
custom repository of type **Integration**. Install and restart Home Assistant.
The badge does not imply a public catalog listing.

## Quick start

1. Add **bunq** under **Settings → Devices & services → Add integration**.
2. Complete the OAuth2 setup for your bunq account.
3. Inspect your account balance and transaction sensors.
