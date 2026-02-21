// ============================================================================
// Application Insights + Log Analytics Workspace
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name prefix for the monitoring resources')
param name string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags')
param tags object = {}

// Configuration based on environment
var logRetentionDays = environment == 'prod' ? 90 : 30
var dailyCapGb = environment == 'prod' ? 10 : 1
var logAnalyticsSku = 'PerGB2018'

// Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${name}-logs'
  location: location
  tags: tags
  properties: {
    sku: {
      name: logAnalyticsSku
    }
    retentionInDays: logRetentionDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: dailyCapGb
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: logRetentionDays
    DisableIpMasking: false
    SamplingPercentage: environment == 'prod' ? 100 : 100
  }
}

// Outputs
@description('The Application Insights instrumentation key')
output instrumentationKey string = appInsights.properties.InstrumentationKey

@description('The Application Insights connection string')
output connectionString string = appInsights.properties.ConnectionString

@description('The Application Insights app ID')
output appId string = appInsights.properties.AppId

@description('The Log Analytics workspace ID (customer ID)')
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.properties.customerId

@description('The Log Analytics workspace shared key')
@secure()
output logAnalyticsSharedKey string = logAnalyticsWorkspace.listKeys().primarySharedKey

@description('The Log Analytics workspace resource ID')
output logAnalyticsResourceId string = logAnalyticsWorkspace.id

@description('The Application Insights resource ID')
output resourceId string = appInsights.id

@description('The Application Insights name')
output name string = appInsights.name
