// Luna XI: Azure infrastructure. Container Apps API (managed identity) · Static Web Apps · Key Vault (RBAC)
// Event Hubs → Functions → Cosmos DB · Service Bus → Functions → Blob + Logic App → Teams · Log Analytics + App Insights · ACR
targetScope = 'resourceGroup'

param prefix string = 'lunaxi'
param location string = resourceGroup().location
param swaLocation string = 'westeurope'
param apiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
param foundryEndpoint string
@secure()
param foundryApiKey string
param fastDeployment string = 'gpt-6-luna'
param reasoningDeployment string = 'gpt-6-sol'
param transcribeDeployment string = 'gpt-transcribe'
param realtimeDeployment string = 'gpt-realtime-2.1'
param decisionDeployment string = 'microsoft-decision-1'
param decisionMode string = 'chat'
param authMode string = 'demo'
param entraTenantId string = tenant().tenantId
param entraApiClientId string = ''
@secure()
param teamsWebhookUrl string = ''

var suffix = uniqueString(resourceGroup().id)
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  ehSender: '2b629674-e913-4c01-ae53-ef4638d8f975'
  ehReceiver: 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde'
  sbSender: '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
  sbReceiver: '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
  blobOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = { name: '${prefix}-logs-${suffix}', location: location, properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 } }
resource appi 'Microsoft.Insights/components@2020-02-02' = { name: '${prefix}-appi-${suffix}', location: location, kind: 'web', properties: { Application_Type: 'web', WorkspaceResourceId: logs.id } }
resource apiId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${prefix}-api-id', location: location }
resource fnId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${prefix}-fn-id', location: location }
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = { name: '${prefix}acr${suffix}', location: location, sku: { name: 'Basic' }, properties: { adminUserEnabled: false } }

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${prefix}-kv-${take(suffix, 8)}'
  location: location
  properties: { tenantId: subscription().tenantId, sku: { family: 'A', name: 'standard' }, enableRbacAuthorization: true, enableSoftDelete: true, enablePurgeProtection: true }
}
resource kvFoundry 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = { parent: kv, name: 'foundry-api-key', properties: { value: foundryApiKey } }
resource kvTicket 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = { parent: kv, name: 'stream-ticket-secret', properties: { value: uniqueString(subscription().id, suffix, 'ticket') } }

resource eh 'Microsoft.EventHub/namespaces@2024-01-01' = { name: '${prefix}-eh-${suffix}', location: location, sku: { name: 'Standard', tier: 'Standard', capacity: 1 }, properties: { disableLocalAuth: true } }
resource ehHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = { parent: eh, name: 'match-events', properties: { partitionCount: 4, messageRetentionInDays: 1 } }
resource ehCg 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = { parent: ehHub, name: 'moment-detector' }
resource sb 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = { name: '${prefix}-sb-${suffix}', location: location, sku: { name: 'Standard', tier: 'Standard' }, properties: { disableLocalAuth: true } }
resource sbTopic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = { parent: sb, name: 'luna-packages' }
resource sbSubPub 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2022-10-01-preview' = { parent: sbTopic, name: 'publisher', properties: { maxDeliveryCount: 5, deadLetteringOnMessageExpiration: true } }
resource sbSubNotify 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2022-10-01-preview' = { parent: sbTopic, name: 'notify', properties: { maxDeliveryCount: 5, deadLetteringOnMessageExpiration: true } }
resource sbQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = { parent: sb, name: 'moments-queue', properties: { maxDeliveryCount: 5, deadLetteringOnMessageExpiration: true } }

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: '${prefix}-cosmos-${suffix}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: { databaseAccountOfferType: 'Standard', capabilities: [ { name: 'EnableServerless' } ], locations: [ { locationName: location, failoverPriority: 0 } ], disableLocalAuth: true }
}
resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = { parent: cosmos, name: 'luna', properties: { resource: { id: 'luna' } } }
resource cosmosMoments 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = { parent: cosmosDb, name: 'moments', properties: { resource: { id: 'moments', partitionKey: { paths: [ '/matchId' ], kind: 'Hash' } } } }

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = { name: '${prefix}st${take(suffix, 10)}', location: location, sku: { name: 'Standard_LRS' }, kind: 'StorageV2', properties: { allowBlobPublicAccess: false, allowSharedKeyAccess: false, minimumTlsVersion: 'TLS1_2' } }
resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = { parent: storage, name: 'default' }
resource published 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = { parent: blobSvc, name: 'published' }
resource fnDeploy 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = { parent: blobSvc, name: 'fn-deploy' }

resource raAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(acr.id, apiId.id, 'acr'), scope: acr, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull), principalId: apiId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(kv.id, apiId.id, 'kv'), scope: kv, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsUser), principalId: apiId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raApiEh 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(eh.id, apiId.id, 'ehs'), scope: eh, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.ehSender), principalId: apiId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raApiSb 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(sb.id, apiId.id, 'sbs'), scope: sb, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.sbSender), principalId: apiId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raFnEh 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(eh.id, fnId.id, 'ehr'), scope: eh, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.ehReceiver), principalId: fnId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raFnSbR 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(sb.id, fnId.id, 'sbr'), scope: sb, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.sbReceiver), principalId: fnId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raFnSbS 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(sb.id, fnId.id, 'sbs'), scope: sb, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.sbSender), principalId: fnId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raFnBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = { name: guid(storage.id, fnId.id, 'blob'), scope: storage, properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobOwner), principalId: fnId.properties.principalId, principalType: 'ServicePrincipal' } }
resource raFnCosmos 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = { parent: cosmos, name: guid(cosmos.id, fnId.id, 'cosmos'), properties: { roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002', principalId: fnId.properties.principalId, scope: cosmos.id } }

resource logic 'Microsoft.Logic/workflows@2019-05-01' = { name: '${prefix}-editorial-${suffix}', location: location, properties: { state: 'Enabled', definition: loadJsonContent('../logicapps/editorial-approval.workflow.json').definition, parameters: { teamsWebhookUrl: { value: teamsWebhookUrl } } } }
resource swa 'Microsoft.Web/staticSites@2023-12-01' = { name: '${prefix}-web-${suffix}', location: swaLocation, sku: { name: 'Free', tier: 'Free' }, properties: {} }
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = { name: '${prefix}-env-${suffix}', location: location, properties: { appLogsConfiguration: { destination: 'log-analytics', logAnalyticsConfiguration: { customerId: logs.properties.customerId, sharedKey: logs.listKeys().primarySharedKey } } } }

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-api'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${apiId.id}': {} } }
  dependsOn: [ raAcr, raKv ]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto', corsPolicy: { allowedOrigins: [ 'https://${swa.properties.defaultHostname}' ], allowedMethods: [ 'GET', 'POST' ], allowedHeaders: [ '*' ] } }
      registries: startsWith(apiImage, acr.properties.loginServer) ? [ { server: acr.properties.loginServer, identity: apiId.id } ] : []
      secrets: [
        { name: 'foundry-api-key', keyVaultUrl: kvFoundry.properties.secretUri, identity: apiId.id }
        { name: 'stream-ticket-secret', keyVaultUrl: kvTicket.properties.secretUri, identity: apiId.id }
        { name: 'appi-conn', value: appi.properties.ConnectionString }
      ]
    }
    template: {
      containers: [ {
        name: 'api'
        image: apiImage
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'AUTH_MODE', value: authMode }
          { name: 'ENTRA_TENANT_ID', value: entraTenantId }
          { name: 'ENTRA_API_CLIENT_ID', value: entraApiClientId }
          { name: 'AZURE_CLIENT_ID', value: apiId.properties.clientId }
          { name: 'KEY_VAULT_URI', value: kv.properties.vaultUri }
          { name: 'FOUNDRY_ENDPOINT', value: foundryEndpoint }
          { name: 'FOUNDRY_API_KEY', secretRef: 'foundry-api-key' }
          { name: 'STREAM_TICKET_SECRET', secretRef: 'stream-ticket-secret' }
          { name: 'FOUNDRY_FAST_DEPLOYMENT', value: fastDeployment }
          { name: 'FOUNDRY_REASONING_DEPLOYMENT', value: reasoningDeployment }
          { name: 'FOUNDRY_TRANSCRIBE_DEPLOYMENT', value: transcribeDeployment }
          { name: 'FOUNDRY_REALTIME_DEPLOYMENT', value: realtimeDeployment }
          { name: 'FOUNDRY_DECISION_DEPLOYMENT', value: decisionDeployment }
          { name: 'FOUNDRY_DECISION_MODE', value: decisionMode }
          { name: 'EVENTHUB_FQDN', value: '${eh.name}.servicebus.windows.net' }
          { name: 'SERVICEBUS_FQDN', value: '${sb.name}.servicebus.windows.net' }
          { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appi-conn' }
          { name: 'CORS_ORIGINS', value: 'https://${swa.properties.defaultHostname}' }
        ]
        probes: [ { type: 'Liveness', httpGet: { path: '/health', port: 8000 }, periodSeconds: 30 } ]
      } ]
      scale: { minReplicas: 0, maxReplicas: 5, rules: [ { name: 'http', http: { metadata: { concurrentRequests: '30' } } } ] }
    }
  }
}

resource fnPlan 'Microsoft.Web/serverfarms@2023-12-01' = { name: '${prefix}-fn-plan', location: location, kind: 'functionapp', sku: { tier: 'FlexConsumption', name: 'FC1' }, properties: { reserved: true } }
resource fn 'Microsoft.Web/sites@2023-12-01' = {
  name: '${prefix}-fn-${suffix}'
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${fnId.id}': {} } }
  dependsOn: [ raFnBlob ]
  properties: {
    serverFarmId: fnPlan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: { storage: { type: 'blobContainer', value: '${storage.properties.primaryEndpoints.blob}fn-deploy', authentication: { type: 'UserAssignedIdentity', userAssignedIdentityResourceId: fnId.id } } }
      scaleAndConcurrency: { maximumInstanceCount: 40, instanceMemoryMB: 2048 }
      runtime: { name: 'python', version: '3.11' }
    }
    siteConfig: { appSettings: [
      { name: 'AzureWebJobsStorage__accountName', value: storage.name }
      { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
      { name: 'AzureWebJobsStorage__clientId', value: fnId.properties.clientId }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appi.properties.ConnectionString }
      { name: 'EVENTHUB_NAME', value: ehHub.name }
      { name: 'SERVICEBUS_TOPIC', value: sbTopic.name }
      { name: 'EventHub__fullyQualifiedNamespace', value: '${eh.name}.servicebus.windows.net' }
      { name: 'EventHub__credential', value: 'managedidentity' }
      { name: 'EventHub__clientId', value: fnId.properties.clientId }
      { name: 'ServiceBus__fullyQualifiedNamespace', value: '${sb.name}.servicebus.windows.net' }
      { name: 'ServiceBus__credential', value: 'managedidentity' }
      { name: 'ServiceBus__clientId', value: fnId.properties.clientId }
      { name: 'Cosmos__accountEndpoint', value: cosmos.properties.documentEndpoint }
      { name: 'Cosmos__credential', value: 'managedidentity' }
      { name: 'Cosmos__clientId', value: fnId.properties.clientId }
      { name: 'Storage__blobServiceUri', value: storage.properties.primaryEndpoints.blob }
      { name: 'Storage__credential', value: 'managedidentity' }
      { name: 'Storage__clientId', value: fnId.properties.clientId }
      { name: 'LOGIC_APP_URL', value: listCallbackUrl('${logic.id}/triggers/package_event', '2019-05-01').value }
      { name: 'LUNA_API_URL', value: 'https://${api.properties.configuration.ingress.fqdn}' }
    ] }
  }
}

output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output webUrl string = 'https://${swa.properties.defaultHostname}'
output acrLoginServer string = acr.properties.loginServer
output keyVaultUri string = kv.properties.vaultUri
output staticWebAppName string = swa.name
output functionAppName string = fn.name
