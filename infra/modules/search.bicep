// ============================================================================
// Azure AI Search (Cognitive Search)
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the Azure AI Search service')
param name string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// SKU configuration based on environment
// Free tier for dev (1 index, 50MB), Basic for prod (15 indexes, 2GB)
var skuName = environment == 'prod' ? 'basic' : 'free'
var replicaCount = environment == 'prod' ? 2 : 1
var partitionCount = environment == 'prod' ? 1 : 1

resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: 'default'
    publicNetworkAccess: environment == 'prod' ? 'disabled' : 'enabled'
    semanticSearch: environment == 'prod' ? 'standard' : 'disabled'
  }
}

// Outputs
@description('The Azure AI Search endpoint URL')
output endpoint string = 'https://${searchService.name}.search.windows.net'

@description('The Azure AI Search admin key')
@secure()
output adminKey string = searchService.listAdminKeys().primaryKey

@description('The Azure AI Search query key')
@secure()
output queryKey string = searchService.listQueryKeys().value[0].key

@description('The Azure AI Search resource ID')
output resourceId string = searchService.id

@description('The Azure AI Search service name')
output name string = searchService.name
