#!/bin/bash
docker pull ghcr.io/hyperledger/aries-cloudagent-python:py3.9-0.12.6

docker run -it --rm \
  -p 8020:8020 -p 8031:8031 \
  ghcr.io/hyperledger/aries-cloudagent-python:py3.9-0.12.6 start \
  --inbound-transport http 0.0.0.0 8020 \
  --outbound-transport http \
  --admin 0.0.0.0 8031 \
  --admin-insecure-mode \
  --webhook-url http://host.docker.internal:8051/webhooks \
  --label "FreshAgent" \
  --wallet-type askar \
  --wallet-name fresh_wallet \
  --wallet-key fresh123 \
  --auto-provision \
  --auto-accept-invites \
  --auto-respond-credential-offer \
  --auto-respond-credential-request \
  --auto-respond-presentation-request \
  --no-ledger --endpoint http://localhost:8020

exit 0