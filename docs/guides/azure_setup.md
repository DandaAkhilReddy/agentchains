# Azure Setup Guide

## Prerequisites

- Azure subscription with Contributor access
- Azure CLI (`az`) installed and authenticated
- Docker installed (for building container images)

## Quick Start (Development)

### 1. Deploy Infrastructure

```bash
# Login to Azure
az login

# Deploy dev environment
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters @infra/parameters.dev.json \
  --parameters tenantId=$(az account show --query tenantId -o tsv)
```

### 2. Get Connection Strings

After deployment, retrieve outputs:

```bash
RG="rg-agentchains-dev"

# PostgreSQL
az postgres flexible-server show -g $RG -n agentchains-pg-dev --query fullyQualifiedDomainName -o tsv

# Redis
az redis show -g $RG -n agentchains-redis-dev --query hostName -o tsv
az redis list-keys -g $RG -n agentchains-redis-dev --query primaryKey -o tsv

# Storage
az storage account show-connection-string -g $RG -n agentchainsstoragedev -o tsv

# Key Vault
az keyvault show -g $RG -n agentchains-kv-dev --query properties.vaultUri -o tsv

# Service Bus
az servicebus namespace authorization-rule keys list -g $RG --namespace-name agentchains-sb-dev -n app-rule --query primaryConnectionString -o tsv
```

### 3. Configure Environment

Create `.env` with Azure connection strings:

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://admin:password@host:5432/agentchains
REDIS_URL=rediss://:key@host:6380/0
AZURE_BLOB_CONNECTION=DefaultEndpointsProtocol=https;...
AZURE_BLOB_CONTAINER=content-store
AZURE_KEYVAULT_URL=https://agentchains-kv-dev.vault.azure.net/
AZURE_SERVICEBUS_CONNECTION=Endpoint=sb://...
AZURE_SEARCH_ENDPOINT=https://agentchains-search-dev.search.windows.net
AZURE_SEARCH_KEY=...
AZURE_APPINSIGHTS_CONNECTION=InstrumentationKey=...
```

### 4. Run Locally

```bash
pip install -r requirements.txt
uvicorn marketplace.main:app --reload
```

## Production Deployment

### 1. Build Container Image

```bash
az acr build --registry agentchainsacr --image agentchains:latest .
```

### 2. Deploy Infrastructure

```bash
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters @infra/parameters.prod.json
```

### 3. Deploy to Container Apps

The GitHub Actions workflow (`.github/workflows/deploy.yml`) handles this automatically on push to master.

## Azure Services

| Service | Purpose | Dev SKU | Prod SKU |
|---------|---------|---------|----------|
| Container Apps | App hosting | Consumption (free tier) | Consumption (auto-scale) |
| PostgreSQL Flexible | Database | Burstable B1ms | General Purpose D2ds_v4 |
| Cache for Redis | Rate limiting, sessions | Basic C0 | Standard C1 |
| Blob Storage | Content store | Standard LRS | Standard GRS |
| Key Vault | Secrets | Standard | Premium |
| AI Search | Full-text search | Free | Basic |
| Service Bus | Message queues | Basic | Standard |
| Application Insights | Monitoring | Pay-as-you-go | Pay-as-you-go |
| OpenAI | AI agents | S0 (10K TPM) | S0 (80K TPM) |

## Cost Estimates

- **Development:** ~$50-75/month
- **Production (single region):** ~$450-650/month
- **Production (multi-region):** ~$700-1,000/month
