// ============================================================================
// Azure Database for PostgreSQL Flexible Server
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the PostgreSQL server')
param serverName string

@description('Administrator login name')
@secure()
param adminLogin string

@description('Administrator login password')
@secure()
param adminPassword string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// SKU configuration based on environment
var skuName = environment == 'prod' ? 'Standard_D2ds_v4' : 'Standard_B1ms'
var skuTier = environment == 'prod' ? 'GeneralPurpose' : 'Burstable'
var storageSizeGB = environment == 'prod' ? 128 : 32
var backupRetentionDays = environment == 'prod' ? 35 : 7
var highAvailabilityMode = environment == 'prod' ? 'ZoneRedundant' : 'Disabled'

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: serverName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: '16'
    administratorLogin: adminLogin
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: storageSizeGB
      autoGrow: environment == 'prod' ? 'Enabled' : 'Disabled'
    }
    backup: {
      backupRetentionDays: backupRetentionDays
      geoRedundantBackup: environment == 'prod' ? 'Enabled' : 'Disabled'
    }
    highAvailability: {
      mode: highAvailabilityMode
    }
    authConfig: {
      activeDirectoryAuth: 'Disabled'
      passwordAuth: 'Enabled'
    }
  }
}

// Firewall rule: Allow Azure services
resource firewallRuleAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Default database for the application
resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgresServer
  name: 'agentchains'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Enable pgvector extension for AI embeddings
resource pgvectorConfig 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgresServer
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR,UUID-OSSP,PGCRYPTO'
    source: 'user-override'
  }
}

// Outputs
@description('The fully qualified domain name of the PostgreSQL server')
output fqdn string = postgresServer.properties.fullyQualifiedDomainName

@description('The PostgreSQL connection string (without password)')
@secure()
output connectionString string = 'postgresql://${adminLogin}@${postgresServer.properties.fullyQualifiedDomainName}:5432/agentchains?sslmode=require'

@description('The PostgreSQL server resource ID')
output resourceId string = postgresServer.id

@description('The PostgreSQL server name')
output name string = postgresServer.name
