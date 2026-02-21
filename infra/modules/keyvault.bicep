// ============================================================================
// Azure Key Vault
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the Key Vault')
param name string

@description('Azure AD tenant ID for the Key Vault')
param tenantId string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// Configuration based on environment
var skuName = environment == 'prod' ? 'premium' : 'standard'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: tenantId
    sku: {
      family: 'A'
      name: skuName
    }
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: environment == 'prod' ? 90 : 7
    enablePurgeProtection: environment == 'prod' ? true : null
    publicNetworkAccess: environment == 'prod' ? 'Disabled' : 'Enabled'
    networkAcls: {
      defaultAction: environment == 'prod' ? 'Deny' : 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Outputs
@description('The Key Vault URI')
output vaultUri string = keyVault.properties.vaultUri

@description('The Key Vault name')
output name string = keyVault.name

@description('The Key Vault resource ID')
output resourceId string = keyVault.id
