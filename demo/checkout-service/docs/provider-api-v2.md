# Payment provider API v2 (effective this release)

Charge responses changed shape:

| v1 field         | v2 field |
|------------------|----------|
| `status`         | `state`  |
| `transaction_id` | `id`     |
| `amount_cents`   | `amount` |

`state` is one of `succeeded`, `declined`.
