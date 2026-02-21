// ============================================================================
// AgentChains — Main Infrastructure Orchestrator
// Sprint 1.1: Azure Infrastructure as Code (Bicep)
//
// Deploys all Azure resources required for the AgentChains platform.
// Usage:
//   az deployment sub create \
//     --location eastus \
//     --template-file infra/main.bicep \
//     --parameters @infra/parameters.dev.json
// ============================================================================

targetScope = 'subscription'

// ============================================================================
// Parameters
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Project name used for resource naming')
@minLength(3)
@maxLength(20)
param projectName string = 'agentchains'

@description('Azure AD tenant ID (required for Key Vault)')
param tenantId string

@description('PostgreSQL administrator login')
@secure()
param postgresAdminLogin string

@description('PostgreSQL administrator password')
@secure()
param postgresAdminPassword string

@description('JWT secret key for authentication')
@secure()
param jwtSecretKey string = ''

@description('Event signing secret for webhook verification')
@secure()
param eventSigningSecret string = ''

@description('Memory encryption key for secure storage')
@secure()
param memoryEncryptionKey string = ''

@description('Container image to deploy')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// ============================================================================
// Variables
// ============================================================================

var resourceGroupName = 'rg-${projectName}-${environment}'
var tags = {
  project: projectName
  environment: environment
  managedBy: 'bicep'
  createdDate: '2026-02-21'
}

// Resource naming (Azure naming conventions)
var postgresServerName = '${projectName}-pg-${environment}'
var redisName = '${projectName}-redis-${environment}'
var storageAccountName = replace('${projectName}st${environment}', '-', '')
var keyVaultName = '${projectName}-kv-${environment}'
var containerAppName = '${projectName}-app-${environment}'
var searchName = '${projectName}-search-${environment}'
var serviceBusName = '${projectName}-sb-${environment}'
var insightsName = '${projectName}-insights-${environment}'
var openAiName = '${projectName}-openai-${environment}'
var acrName = replace('${projectName}acr${environment}', '-', '')

// ============================================================================
// Resource Group
// ============================================================================

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// ============================================================================
// Module Deployments
// ============================================================================

// --- Monitoring (deployed first, outputs used by other modules) ---
module insights 'modules/insights.bicep' = {
  name: 'deploy-insights'
  scope: resourceGroup
  params: {
    location: location
    name: insightsName
    environment: environment
    tags: tags
  }
}

// --- Data Layer ---
module postgres 'modules/postgres.bicep' = {
  name: 'deploy-postgres'
  scope: resourceGroup
  params: {
    location: location
    serverName: postgresServerName
    adminLogin: postgresAdminLogin
    adminPassword: postgresAdminPassword
    environment: environment
    tags: tags
  }
}

module redis 'modules/redis.bicep' = {
  name: 'deploy-redis'
  scope: resourceGroup
  params: {
    location: location
    name: redisName
    environment: environment
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'deploy-storage'
  scope: resourceGroup
  params: {
    location: location
    storageAccountName: storageAccountName
    environment: environment
    tags: tags
  }
}

// --- Security ---
module keyvault 'modules/keyvault.bicep' = {
  name: 'deploy-keyvault'
  scope: resourceGroup
  params: {
    location: location
    name: keyVaultName
    tenantId: tenantId
    environment: environment
    tags: tags
  }
}

// --- AI Services ---
module search 'modules/search.bicep' = {
  name: 'deploy-search'
  scope: resourceGroup
  params: {
    location: location
    name: searchName
    environment: environment
    tags: tags
  }
}

module openai 'modules/openai.bicep' = {
  name: 'deploy-openai'
  scope: resourceGroup
  params: {
    location: location
    name: openAiName
    environment: environment
    tags: tags
  }
}

// --- Messaging ---
module servicebus 'modules/servicebus.bicep' = {
  name: 'deploy-servicebus'
  scope: resourceGroup
  params: {
    location: location
    namespaceName: serviceBusName
    environment: environment
    tags: tags
  }
}

// --- Container Registry ---
module acr 'modules/acr.bicep' = {
  name: 'deploy-acr'
  scope: resourceGroup
  params: {
    location: location
    name: acrName
    environment: environment
    tags: tags
  }
}

// --- Compute (dependencies inferred from module output references) ---
module containerapp 'modules/containerapp.bicep' = {
  name: 'deploy-containerapp'
  scope: resourceGroup
  params: {
    location: location
    name: containerAppName
    environment: environment
    containerImage: containerImage
    registryLoginServer: acr.outputs.loginServer
    registryUsername: acr.outputs.adminUsername
    registryPassword: acr.outputs.adminPassword
    logAnalyticsWorkspaceId: insights.outputs.logAnalyticsWorkspaceId
    logAnalyticsSharedKey: insights.outputs.logAnalyticsSharedKey
    corsOrigins: environment == 'prod' ? [
      'https://agentchains.ai'
      'https://www.agentchains.ai'
    ] : [
      '*'
    ]
    tags: tags
    envVars: [
      {
        name: 'ENVIRONMENT'
        value: environment
      }
      {
        name: 'DATABASE_URL'
        value: 'postgresql+asyncpg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres.outputs.fqdn}:5432/agentchains?ssl=require'
      }
      {
        name: 'REDIS_URL'
        value: 'rediss://:${redis.outputs.primaryKey}@${redis.outputs.hostName}:${redis.outputs.sslPort}/0'
      }
      {
        name: 'JWT_SECRET_KEY'
        value: jwtSecretKey
      }
      {
        name: 'EVENT_SIGNING_SECRET'
        value: eventSigningSecret
      }
      {
        name: 'MEMORY_ENCRYPTION_KEY'
        value: memoryEncryptionKey
      }
      {
        name: 'CORS_ORIGINS'
        value: environment == 'prod' ? 'https://agentchains.ai,https://www.agentchains.ai' : '*'
      }
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: insights.outputs.connectionString
      }
      {
        name: 'AZURE_KEYVAULT_URL'
        value: keyvault.outputs.vaultUri
      }
      {
        name: 'POSTGRES_HOST'
        value: postgres.outputs.fqdn
      }
      {
        name: 'POSTGRES_DB'
        value: 'agentchains'
      }
      {
        name: 'REDIS_HOST'
        value: redis.outputs.hostName
      }
      {
        name: 'REDIS_PORT'
        value: string(redis.outputs.sslPort)
      }
      {
        name: 'AZURE_STORAGE_ENDPOINT'
        value: storage.outputs.primaryBlobEndpoint
      }
      {
        name: 'AZURE_BLOB_CONNECTION'
        value: storage.outputs.connectionString
      }
      {
        name: 'AZURE_SEARCH_ENDPOINT'
        value: search.outputs.endpoint
      }
      {
        name: 'AZURE_SEARCH_KEY'
        value: search.outputs.adminKey
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: openai.outputs.endpoint
      }
      {
        name: 'AZURE_OPENAI_DEPLOYMENT'
        value: openai.outputs.gpt4oDeploymentName
      }
      {
        name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
        value: openai.outputs.embeddingDeploymentName
      }
      {
        name: 'AZURE_SERVICEBUS_CONNECTION'
        value: servicebus.outputs.connectionString
      }
      {
        name: 'SERVICEBUS_NAMESPACE'
        value: servicebus.outputs.namespaceName
      }
    ]
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('The resource group name')
output resourceGroupName string = resourceGroup.name

@description('The ACR login server')
output acrLoginServer string = acr.outputs.loginServer

@description('The Container App URL')
output containerAppUrl string = containerapp.outputs.url

@description('The Container App FQDN')
output containerAppFqdn string = containerapp.outputs.fqdn

@description('The PostgreSQL server FQDN')
output postgresFqdn string = postgres.outputs.fqdn

@description('The Redis hostname')
output redisHostName string = redis.outputs.hostName

@description('The Storage blob endpoint')
output storageBlobEndpoint string = storage.outputs.primaryBlobEndpoint

@description('The Key Vault URI')
output keyVaultUri string = keyvault.outputs.vaultUri

@description('The Azure AI Search endpoint')
output searchEndpoint string = search.outputs.endpoint

@description('The Azure OpenAI endpoint')
output openAiEndpoint string = openai.outputs.endpoint

@description('The Service Bus endpoint')
output serviceBusEndpoint string = servicebus.outputs.endpoint

@description('The Application Insights connection string')
output appInsightsConnectionString string = insights.outputs.connectionString

@description('The Log Analytics workspace ID')
output logAnalyticsWorkspaceId string = insights.outputs.logAnalyticsWorkspaceId
