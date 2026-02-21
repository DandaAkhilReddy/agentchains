// ============================================================================
// Azure OpenAI Service + GPT-4o Deployment
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the Azure OpenAI account')
param name string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// Configuration based on environment
var skuName = 'S0'
var gpt4oCapacity = environment == 'prod' ? 80 : 10
var embeddingCapacity = environment == 'prod' ? 120 : 10

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: skuName
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: environment == 'prod' ? 'Disabled' : 'Enabled'
    networkAcls: {
      defaultAction: environment == 'prod' ? 'Deny' : 'Allow'
    }
  }
}

// GPT-4o model deployment
resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAiAccount
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: gpt4oCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// Text embedding model for vector search / RAG
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAiAccount
  name: 'text-embedding-3-large'
  dependsOn: [gpt4oDeployment]
  sku: {
    name: 'Standard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// Outputs
@description('The Azure OpenAI endpoint')
output endpoint string = openAiAccount.properties.endpoint

@description('The Azure OpenAI primary key')
output primaryKey string = openAiAccount.listKeys().key1

@description('The Azure OpenAI resource ID')
output resourceId string = openAiAccount.id

@description('The Azure OpenAI account name')
output name string = openAiAccount.name

@description('The GPT-4o deployment name')
output gpt4oDeploymentName string = gpt4oDeployment.name

@description('The embedding deployment name')
output embeddingDeploymentName string = embeddingDeployment.name
