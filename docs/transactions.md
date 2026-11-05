# Transactions

Each monetary-account sensor reports a balance and a `transactions` attribute.
You can render the latter in a custom
[HTML template card](https://github.com/piotrmachowski/home-assistant-lovelace-html-jinja2-template-card),
if that card is installed. Replace the example entity with your own:

```yaml
type: custom:html-template-card
title: Transactions
ignore_line_breaks: true
content: >
  <table>
    <tr><th>Amount</th><th>Description</th><th>Time</th></tr>
    {% for transaction in state_attr('sensor.bunq_example', 'transactions') %}
    <tr>
      <td>{{ transaction.amount }} {{ transaction.currency }}</td>
      <td>{{ transaction.description }}</td>
      <td>{{ strptime(transaction.created, '%Y-%m-%d %H:%M:%S.%f') | relative_time }}</td>
    </tr>
    {% endfor %}
  </table>
```
