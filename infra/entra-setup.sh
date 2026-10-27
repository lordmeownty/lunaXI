#!/usr/bin/env bash
# OPTIONAL: real Microsoft Entra ID app registration (SPA + API scope + 6 app roles incl. Luna.Director; assigns you Director).
# The hackathon demo uses the simulated "Sign in with Microsoft" button and does NOT need this.
set -euo pipefail
NAME="${APP_NAME:-Luna XI}"; WEB_URL="${WEB_URL:-http://localhost:5173}"
APP_ID=$(az ad app create --display-name "$NAME" --sign-in-audience AzureADMyOrg --query appId -o tsv)
OBJ_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)
az ad app update --id "$APP_ID" --identifier-uris "api://$APP_ID"
BODY=$(python3 - "$WEB_URL" <<'PY'
import json, sys, uuid
roles=[("Luna.Fan","Fan"),("Luna.Analyst","Analyst"),("Luna.Broadcaster","Broadcaster"),("Luna.Editor","Editor"),("Luna.Admin","Administrator"),("Luna.Director","Director (all access)")]
print(json.dumps({"spa":{"redirectUris":sorted({sys.argv[1],"http://localhost:5173"})},
 "api":{"requestedAccessTokenVersion":2,"oauth2PermissionScopes":[{"id":str(uuid.uuid4()),"value":"access_as_user","type":"User","isEnabled":True,
   "adminConsentDisplayName":"Access Luna XI","adminConsentDescription":"Call the Luna XI API as the signed-in user.","userConsentDisplayName":"Access Luna XI","userConsentDescription":"Use Luna XI on your behalf."}]},
 "appRoles":[{"id":str(uuid.uuid4()),"value":v,"displayName":d,"description":d,"isEnabled":True,"allowedMemberTypes":["User"]} for v,d in roles]}))
PY
)
az rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$OBJ_ID" --headers "Content-Type=application/json" --body "$BODY"
SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv 2>/dev/null || az ad sp show --id "$APP_ID" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
ROLE=$(az ad app show --id "$APP_ID" --query "appRoles[?value=='Luna.Director'].id | [0]" -o tsv)
az rest --method POST --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_ID/appRoleAssignedTo" --body "{\"principalId\":\"$ME\",\"resourceId\":\"$SP_ID\",\"appRoleId\":\"$ROLE\"}" >/dev/null
echo "ENTRA_TENANT_ID=$(az account show --query tenantId -o tsv)"; echo "ENTRA_API_CLIENT_ID=$APP_ID"
