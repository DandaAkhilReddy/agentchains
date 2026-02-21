// ============================================================================
// Azure Cache for Redis
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the Redis cache instance')
param name string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// SKU configuration based on environment
var skuName = environment == 'prod' ? 'Standard' : 'Basic'
var skuFamily = 'C'
var skuCapacity = environment == 'prod' ? 1 : 0

resource redisCache 'Microsoft.Cache/redis@2023-08-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: skuName
      family: skuFamily
      capacity: skuCapacity
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisConfiguration: {
      'maxmemory-policy': 'allkeys-lru'
    }
    publicNetworkAccess: environment == 'prod' ? 'Disabled' : 'Enabled'
  }
}

// Outputs
@description('The hostname of the Redis cache')
output hostName string = redisCache.properties.hostName

@description('The SSL port of the Redis cache')
output sslPort int = redisCache.properties.sslPort

@description('The primary connection string for Redis')
@secure()
output connectionString string = '${redisCache.properties.hostName}:${redisCache.properties.sslPort},password=${redisCache.listKeys().primaryKey},ssl=True,abortConnect=False'

@description('The primary access key for Redis')
@secure()
output primaryKey string = redisCache.listKeys().primaryKey

@description('The Redis cache resource ID')
output resourceId string = redisCache.id

@description('The Redis cache name')
output name string = redisCache.name
