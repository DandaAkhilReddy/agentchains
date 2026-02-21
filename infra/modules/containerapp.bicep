// ============================================================================
// Azure Container Apps Environment + Application
// AgentChains Infrastructure - Sprint 1.1
// ============================================================================

@description('Azure region for all resources')
param location string

@description('Name of the Container App')
param name string

@description('Deployment environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Container image to deploy')
param containerImage string

@description('Container registry login server')
param registryLoginServer string

@description('Container registry username')
@secure()
param registryUsername string

@description('Container registry password')
@secure()
param registryPassword string

@description('Resource tags')
param tags object = {}

@description('Log Analytics workspace ID for the environment')
param logAnalyticsWorkspaceId string = ''

@description('Log Analytics workspace shared key')
@secure()
param logAnalyticsSharedKey string = ''

@description('Environment variables for the container')
param envVars array = []

@description('CORS allowed origins')
param corsOrigins array = ['*']

// Scaling configuration based on environment
var minReplicas = environment == 'prod' ? 2 : 0
var maxReplicas = environment == 'prod' ? 10 : 2
var cpuCores = '0.25'
var memorySize = '0.5Gi'

// Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${name}-env'
  location: location
  tags: tags
  properties: {
    zoneRedundant: false
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: !empty(logAnalyticsWorkspaceId) ? {
        customerId: logAnalyticsWorkspaceId
        sharedKey: logAnalyticsSharedKey
      } : null
    }
    workloadProfiles: environment == 'prod' ? [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ] : [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        corsPolicy: {
          allowedOrigins: corsOrigins
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          maxAge: 3600
        }
      }
      registries: [
        {
          server: registryLoginServer
          username: registryUsername
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: [
        {
          name: 'registry-password'
          value: registryPassword
        }
      ]
      activeRevisionsMode: environment == 'prod' ? 'Multiple' : 'Single'
    }
    template: {
      containers: [
        {
          name: name
          image: containerImage
          resources: {
            cpu: json(cpuCores)
            memory: memorySize
          }
          env: envVars
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health'
                port: 8080
              }
              initialDelaySeconds: 30
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/v1/health'
                port: 8080
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: environment == 'prod' ? '50' : '10'
              }
            }
          }
        ]
      }
    }
  }
}

// Outputs
@description('The FQDN of the Container App')
output fqdn string = containerApp.properties.configuration.ingress.fqdn

@description('The URL of the Container App')
output url string = 'https://${containerApp.properties.configuration.ingress.fqdn}'

@description('The Container App Environment ID')
output environmentId string = containerAppEnv.id

@description('The Container App resource ID')
output resourceId string = containerApp.id

@description('The Container App name')
output name string = containerApp.name
