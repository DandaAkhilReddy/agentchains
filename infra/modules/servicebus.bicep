// ============================================================================
// Azure Service Bus Namespace + Queues
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the Service Bus namespace')
param namespaceName string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// SKU configuration based on environment
var skuName = environment == 'prod' ? 'Standard' : 'Basic'
var skuTier = environment == 'prod' ? 'Standard' : 'Basic'

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: environment == 'prod' ? 'Disabled' : 'Enabled'
    zoneRedundant: environment == 'prod'
  }
}

// Queue: Webhook events processing
resource webhooksQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'webhooks'
  properties: {
    maxDeliveryCount: 10
    defaultMessageTimeToLive: 'P7D'
    lockDuration: 'PT1M'
    deadLetteringOnMessageExpiration: true
    requiresDuplicateDetection: environment == 'prod'
    duplicateDetectionHistoryTimeWindow: environment == 'prod' ? 'PT10M' : 'PT1M'
    maxSizeInMegabytes: environment == 'prod' ? 5120 : 1024
  }
}

// Queue: Agent orchestration tasks
resource orchestrationQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'orchestration'
  properties: {
    maxDeliveryCount: 5
    defaultMessageTimeToLive: 'P1D'
    lockDuration: 'PT5M'
    deadLetteringOnMessageExpiration: true
    requiresDuplicateDetection: environment == 'prod'
    duplicateDetectionHistoryTimeWindow: environment == 'prod' ? 'PT10M' : 'PT1M'
    maxSizeInMegabytes: environment == 'prod' ? 5120 : 1024
  }
}

// Queue: Agent task results
resource resultsQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'agent-results'
  properties: {
    maxDeliveryCount: 10
    defaultMessageTimeToLive: 'P3D'
    lockDuration: 'PT1M'
    deadLetteringOnMessageExpiration: true
    requiresDuplicateDetection: false
    maxSizeInMegabytes: environment == 'prod' ? 5120 : 1024
  }
}

// Authorization rule for the application
resource appAuthRule 'Microsoft.ServiceBus/namespaces/AuthorizationRules@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'agentchains-app'
  properties: {
    rights: [
      'Send'
      'Listen'
      'Manage'
    ]
  }
}

// Outputs
@description('The Service Bus namespace endpoint')
output endpoint string = serviceBusNamespace.properties.serviceBusEndpoint

@description('The Service Bus connection string')
output connectionString string = appAuthRule.listKeys().primaryConnectionString

@description('The Service Bus namespace name')
output namespaceName string = serviceBusNamespace.name

@description('The Service Bus namespace resource ID')
output resourceId string = serviceBusNamespace.id

@description('The webhooks queue name')
output webhooksQueueName string = webhooksQueue.name

@description('The orchestration queue name')
output orchestrationQueueName string = orchestrationQueue.name

@description('The agent results queue name')
output agentResultsQueueName string = resultsQueue.name
