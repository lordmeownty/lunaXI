#!/usr/bin/env bash
# Deploy: infrastructure (incl. Key Vault) → API image → Functions → frontend.
# Usage: RG=luna-xi-rg LOCATION=swedencentral FOUNDRY_ENDPOINT=... FOUNDRY_API_KEY=... ./infra/deploy.sh
set -euo pipefail
: "${RG:?}"; : "${LOCATION:=swedencentral}"; : "${FOUNDRY_ENDPOINT:?}"; : "${FOUNDRY_API_KEY:?}"
cd "$(dirname "$0")/.."
az group create -n "$RG" -l "$LOCATION" -o none
P=(foundryEndpoint="$FOUNDRY_ENDPOINT" foundryApiKey="$FOUNDRY_API_KEY" teamsWebhookUrl="${TEAMS_WEBHOOK_URL:-}")
OUT=$(az deployment group create -g "$RG" -f infra/main.bicep -p "${P[@]}" --query properties.outputs -o json)
ACR=$(echo "$OUT" | jq -r .acrLoginServer.value); SWA=$(echo "$OUT" | jq -r .staticWebAppName.value)
API=$(echo "$OUT" | jq -r .apiUrl.value); FN=$(echo "$OUT" | jq -r .functionAppName.value)
az acr build -r "${ACR%%.*}" -t luna-xi-api:latest -f backend/Dockerfile .
az deployment group create -g "$RG" -f infra/main.bicep -p "${P[@]}" apiImage="$ACR/luna-xi-api:latest" -o none
( cd functions && func azure functionapp publish "$FN" --python )
( cd frontend && npm install && VITE_API_BASE="$API" npm run build )
npx --yes @azure/static-web-apps-cli deploy frontend/dist --deployment-token "$(az staticwebapp secrets list -n "$SWA" -g "$RG" --query properties.apiKey -o tsv)" --env production
echo "Web: $(echo "$OUT" | jq -r .webUrl.value)  API: $API  Key Vault: $(echo "$OUT" | jq -r .keyVaultUri.value)"
