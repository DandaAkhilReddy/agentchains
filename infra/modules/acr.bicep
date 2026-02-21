// ============================================================================
// Azure Container Registry
// AgentChains Infrastructure
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the Container Registry')
param name string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// Basic SKU for dev, Standard for prod/staging
var skuName = environment == 'dev' ? 'Basic' : 'Standard'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    adminUserEnabled: true
  }
}

// Outputs
@description('The ACR login server (e.g. myacr.azurecr.io)')
output loginServer string = acr.properties.loginServer

@description('The ACR admin username')
output adminUsername string = acr.listCredentials().username

@description('The ACR admin password')
@secure()
output adminPassword string = acr.listCredentials().passwords[0].value

@description('The ACR resource ID')
output resourceId string = acr.id

@description('The ACR name')
output name string = acr.name
