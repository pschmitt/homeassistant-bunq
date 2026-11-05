<p align="center">
  <a href="https://my.home-assistant.io/redirect/marketplace_repository/?owner=pschmitt&amp;repository=homeassistant-bunq&amp;category=integration"><img src="https://my.home-assistant.io/badges/marketplace_repository.svg" alt="Open this integration in Home Assistant Marketplace"></a>
</p>

<h1 align="center">bunq for Home Assistant</h1>

<p align="center">Read bunq account balances and transactions in Home Assistant through OAuth.</p>

## Features

- **Account sensors:** Show monetary-account balances and recent transactions.
- **Card sensors:** Show debit and credit cards with references to linked accounts.
- **Account actions:** Transfer funds between your own accounts and link an account to a card where supported.
- **OAuth configuration:** Connect through the Home Assistant UI instead of a YAML API key. See [OAuth setup](docs/setup.md).

## Install

Use the Marketplace badge above on Home Assistant 2026.11 or later to add this
repository as a custom integration. On older versions, add it as a HACS
custom repository of type **Integration**. Install and restart Home Assistant.
The badge does not imply a public catalog listing. This branch requires Home
Assistant 2023.6.1 or later; see [OAuth setup](docs/setup.md) if upgrading
from the old API-key integration.

## Quick start

1. Add an OAuth redirect URL in your bunq app's developer settings.
2. Add **bunq** under **Settings → Devices & services → Add integration** and enter your OAuth client details.
3. Link your account through the authorization flow and inspect the balance sensors.

## Documentation

| Topic | Description |
|-------|-------------|
| [OAuth setup](docs/setup.md) | Developer-app credentials and upgrade guidance |
| [Transactions](docs/transactions.md) | Sensor transactions and an example dashboard card |
| [Changelog](CHANGELOG.md) | Release history |
