#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8080}"

curl --fail --silent --show-error \
  -X POST "${BASE_URL}/__test__/transactions" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "top_up",
    "card_external_id": "CARD-42",
    "occurred_at": "23.09.2026 14:00:00",
    "fuel": "DT",
    "quantity": "500.00"
  }'
printf '\n'

curl --fail --silent --show-error \
  -X POST "${BASE_URL}/__test__/transactions" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "sale",
    "card_external_id": "CARD-42",
    "occurred_at": "23.09.2026 15:00:00",
    "station": "Station B",
    "transaction_number": "TX-2",
    "dispenser": "2",
    "fuel": "DT",
    "unit_price": "250.00",
    "quantity": "100.00",
    "amount": "25000.00",
    "issuer": "Issuer",
    "holder": "Main card",
    "contract": "Contract"
  }'
printf '\n'