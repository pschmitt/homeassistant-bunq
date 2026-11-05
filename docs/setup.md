# OAuth setup

This branch requires Home Assistant 2023.6.1 or later. To configure bunq OAuth:

1. Open the bunq app and go to **Profile → Developers → OAuth**.
2. Add `https://my.home-assistant.io/redirect/oauth` as a redirect URL.
3. Open **Client details** and use the client ID and secret when adding bunq
   under **Settings → Devices & services → Add integration**.
4. When redirected to `my.home-assistant.io`, enter the address where your
   Home Assistant instance can be reached and select **Link Account**.

The earlier API-key integration (version 1.0.0) used `configuration.yaml` and
is incompatible with OAuth-based releases. If upgrading from that version,
remove the old integration and its YAML configuration before installing the
OAuth-based integration.

OAuth grants narrower permissions than the old API-key setup, which had full
write access to accounts. See the configuration flow for available actions.
