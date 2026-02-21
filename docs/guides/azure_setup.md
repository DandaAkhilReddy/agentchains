# Azure Setup Guide

Deploy the AgentChains platform on Microsoft Azure using Bicep infrastructure-as-code templates.

---

## 1. Prerequisites

| Requirement | Minimum Version | Purpose |
|-------------|----------------|---------|
| Azure Subscription | Pay-as-you-go or higher | Resource provisioning |
| Azure CLI | 2.60+ | Deployment commands |
| Docker | 24+ | Container image builds |
| Git | 2.40+ | Source control |
| Python | 3.12+ | Local development |

Verify your setup:

```bash
az version          # Azure CLI version
az login            # Authenticate
az account show     # Confirm subscription
docker --version    # Docker version
```

---

## 2. Infrastructure Architecture

The Bicep templates in `infra/` deploy the following Azure services:

```
                   +-----------------------+
                   |   Resource Group       |
                   |   rg-agentchains-ENV   |
                   +-----------+-----------+
                               |
          +--------------------+-------------------+
          |                    |                    |
    +-----v-----+      +------v------+     +------v------+
    | Container  |      | PostgreSQL  |     |    Redis    |
    | Apps       |      | Flexible    |     |    Cache    |
    | (Compute)  |      | (Database)  |     | (Sessions)  |
    +-----+-----+      +-------------+     +-------------+
          |
    +-----+-----+----+-------------+
    |           |     |             |
+---v---+ +----v--+ +v--------+ +--v--------+
| Blob  | | Key   | | AI      | | Service   |
| Store | | Vault | | Search  | | Bus       |
+-------+ +-------+ +---------+ +-----------+
    |
+---v--------+    +------------+
| OpenAI     |    | App        |
| (GPT-4o)   |    | Insights   |
+------------+    +------------+
```

### Module Files

| File | Resource | Purpose |
|------|----------|---------|
| `infra/main.bicep` | Resource Group + orchestration | Main deployment template |
| `infra/modules/postgres.bicep` | Azure Database for PostgreSQL Flexible Server | Primary database |
| `infra/modules/redis.bicep` | Azure Cache for Redis | Rate limiting, sessions, caching |
| `infra/modules/storage.bicep` | Azure Storage Account | Blob storage for content-addressed files |
| `infra/modules/keyvault.bicep` | Azure Key Vault | Secrets management |
| `infra/modules/containerapp.bicep` | Azure Container Apps | Application hosting |
| `infra/modules/search.bicep` | Azure AI Search | Full-text search indexing |
| `infra/modules/servicebus.bicep` | Azure Service Bus | Async message queuing |
| `infra/modules/insights.bicep` | Application Insights + Log Analytics | Monitoring and logging |
| `infra/modules/openai.bicep` | Azure OpenAI Service | GPT-4o and embedding models |

### Parameter Files

| File | Environment | Notes |
|------|-------------|-------|
| `infra/parameters.dev.json` | Development | Uses default container image, no ACR |
| `infra/parameters.prod.json` | Production | References ACR, Key Vault secrets |

---

## 3. Development Deployment

### 3.1 Deploy Infrastructure

```bash
# Login to Azure
az login

# Set your subscription (if you have multiple)
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Deploy dev environment
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters @infra/parameters.dev.json \
  --parameters tenantId=$(az account show --query tenantId -o tsv) \
  --parameters postgresAdminLogin=agentchainsadmin \
  --parameters postgresAdminPassword='<YOUR_STRONG_PASSWORD>'
```

The deployment takes approximately 10-15 minutes for all modules.

### 3.2 Retrieve Connection Strings

After deployment, retrieve the outputs:

```bash
RG="rg-agentchains-dev"

# PostgreSQL FQDN
az postgres flexible-server show \
  -g $RG -n agentchains-pg-dev \
  --query fullyQualifiedDomainName -o tsv

# Redis hostname and key
az redis show -g $RG -n agentchains-redis-dev --query hostName -o tsv
az redis list-keys -g $RG -n agentchains-redis-dev --query primaryKey -o tsv

# Storage connection string
az storage account show-connection-string \
  -g $RG -n agentchainsstdev -o tsv

# Key Vault URI
az keyvault show -g $RG -n agentchains-kv-dev \
  --query properties.vaultUri -o tsv

# Service Bus connection string
az servicebus namespace authorization-rule keys list \
  -g $RG --namespace-name agentchains-sb-dev \
  -n RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv

# Application Insights connection string
az monitor app-insights component show \
  -g $RG --app agentchains-insights-dev \
  --query connectionString -o tsv

# OpenAI endpoint
az cognitiveservices account show \
  -g $RG -n agentchains-openai-dev \
  --query properties.endpoint -o tsv

# AI Search endpoint
az search service show \
  -g $RG -n agentchains-search-dev \
  --query "hostName" -o tsv
```

### 3.3 Configure Environment Variables

Create a `.env` file in the project root:

```env
# Environment
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql+asyncpg://agentchainsadmin:<PASSWORD>@agentchains-pg-dev.postgres.database.azure.com:5432/agentchains

# Redis
REDIS_URL=rediss://:<PRIMARY_KEY>@agentchains-redis-dev.redis.cache.windows.net:6380/0

# Azure Blob Storage
AZURE_BLOB_CONNECTION=DefaultEndpointsProtocol=https;AccountName=agentchainsstdev;...
AZURE_BLOB_CONTAINER=content-store

# Azure Key Vault
AZURE_KEYVAULT_URL=https://agentchains-kv-dev.vault.azure.net/

# Azure Service Bus
AZURE_SERVICEBUS_CONNECTION=Endpoint=sb://agentchains-sb-dev.servicebus.windows.net/;...

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://agentchains-search-dev.search.windows.net
AZURE_SEARCH_KEY=<ADMIN_KEY>

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://agentchains-openai-dev.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...

# Security
JWT_SECRET_KEY=<GENERATE_A_STRONG_SECRET>
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# MCP
MCP_ENABLED=true
MCP_RATE_LIMIT_PER_MINUTE=60

# Payment (simulated for dev)
PAYMENT_MODE=simulated
```

### 3.4 Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the server
uvicorn marketplace.main:app --reload --host 0.0.0.0 --port 8000

# Start the frontend (in a separate terminal)
cd frontend && npm install && npm run dev
```

---

## 4. Production Deployment

### 4.1 Create Azure Container Registry

```bash
# Create ACR
az acr create --resource-group rg-agentchains-prod \
  --name agentchainsacr --sku Standard

# Login to ACR
az acr login --name agentchainsacr
```

### 4.2 Build and Push Container Image

```bash
# Build using ACR Tasks (no local Docker needed)
az acr build --registry agentchainsacr \
  --image agentchains:latest \
  --image agentchains:$(git rev-parse --short HEAD) \
  .

# Or build locally and push
docker build -t agentchainsacr.azurecr.io/agentchains:latest .
docker push agentchainsacr.azurecr.io/agentchains:latest
```

### 4.3 Store Secrets in Key Vault

```bash
KV="agentchains-kv-prod"

az keyvault secret set --vault-name $KV \
  --name postgres-admin-password --value '<STRONG_PASSWORD>'

az keyvault secret set --vault-name $KV \
  --name acr-username --value '<ACR_USERNAME>'

az keyvault secret set --vault-name $KV \
  --name acr-password --value '<ACR_PASSWORD>'

az keyvault secret set --vault-name $KV \
  --name jwt-secret-key --value '<GENERATED_SECRET>'

az keyvault secret set --vault-name $KV \
  --name stripe-secret-key --value '<STRIPE_KEY>'

az keyvault secret set --vault-name $KV \
  --name razorpay-key-id --value '<RAZORPAY_KEY>'

az keyvault secret set --vault-name $KV \
  --name razorpay-key-secret --value '<RAZORPAY_SECRET>'
```

### 4.4 Deploy Production Infrastructure

```bash
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters @infra/parameters.prod.json \
  --parameters tenantId=$(az account show --query tenantId -o tsv)
```

### 4.5 Verify Deployment

```bash
# Get the Container App URL
az containerapp show \
  -g rg-agentchains-prod -n agentchains-app-prod \
  --query properties.configuration.ingress.fqdn -o tsv

# Test health endpoint
curl https://<APP_FQDN>/api/v1/health
```

---

## 5. Container Apps Configuration

The Container App receives environment variables from Bicep outputs:

| Environment Variable | Source |
|---------------------|--------|
| `ENVIRONMENT` | Bicep parameter |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights module output |
| `AZURE_KEYVAULT_URL` | Key Vault module output |
| `POSTGRES_HOST` | PostgreSQL module output |
| `POSTGRES_DB` | `agentchains` (hardcoded) |
| `REDIS_HOST` | Redis module output |
| `REDIS_PORT` | Redis SSL port output |
| `AZURE_STORAGE_ENDPOINT` | Storage module output |
| `AZURE_SEARCH_ENDPOINT` | AI Search module output |
| `AZURE_OPENAI_ENDPOINT` | OpenAI module output |
| `AZURE_OPENAI_DEPLOYMENT` | OpenAI GPT-4o deployment name |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | OpenAI embedding deployment name |
| `SERVICEBUS_NAMESPACE` | Service Bus namespace |

---

## 6. Monitoring Setup

### 6.1 Application Insights

Application Insights is deployed automatically via the `insights.bicep` module. It provides:

- Request tracing (via OpenTelemetry auto-instrumentation)
- Dependency tracking (database, Redis, HTTP calls)
- Exception logging
- Performance metrics
- Live metrics stream

Enable OpenTelemetry tracing in the app:

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=agentchains
OTEL_EXPORTER_OTLP_ENDPOINT=<APP_INSIGHTS_INGESTION_ENDPOINT>
```

### 6.2 Log Analytics Queries

```kusto
// Container App request latency (p95)
requests
| where timestamp > ago(1h)
| summarize percentile(duration, 95) by bin(timestamp, 5m)
| render timechart

// Error rate by endpoint
requests
| where timestamp > ago(24h) and success == false
| summarize count() by name
| order by count_ desc

// Database query performance
dependencies
| where type == "SQL"
| summarize avg(duration), count() by name
| order by avg_duration desc
```

### 6.3 Alerts (Recommended)

| Alert | Condition | Severity |
|-------|-----------|----------|
| High error rate | Failure rate > 5% for 5 min | Critical |
| Slow responses | P95 latency > 2s for 5 min | Warning |
| Database connection failures | Dependency failures > 10 in 5 min | Critical |
| Container restart | Restart count > 3 in 10 min | Warning |
| Budget threshold | Monthly spend > 80% of budget | Info |

---

## 7. Cost Estimates

### Development Environment

| Service | SKU | Estimated Monthly Cost |
|---------|-----|----------------------|
| Container Apps | Consumption (free tier) | $0 |
| PostgreSQL Flexible | Burstable B1ms | $13 |
| Redis Cache | Basic C0 | $16 |
| Blob Storage | Standard LRS | $2 |
| Key Vault | Standard | $1 |
| AI Search | Free | $0 |
| Service Bus | Basic | $1 |
| Application Insights | Pay-as-you-go | $5 |
| OpenAI | S0 (10K TPM) | $10-20 |
| **Total** | | **~$50-75/month** |

### Production Environment (Single Region)

| Service | SKU | Estimated Monthly Cost |
|---------|-----|----------------------|
| Container Apps | Consumption (auto-scale) | $50-100 |
| PostgreSQL Flexible | General Purpose D2ds_v4 | $130 |
| Redis Cache | Standard C1 | $80 |
| Blob Storage | Standard GRS | $10 |
| Key Vault | Premium | $3 |
| AI Search | Basic | $75 |
| Service Bus | Standard | $10 |
| Application Insights | Pay-as-you-go | $30-50 |
| OpenAI | S0 (80K TPM) | $60-150 |
| **Total** | | **~$450-650/month** |

### Production Environment (Multi-Region)

Add approximately $250-350/month for secondary region resources and geo-replication.

**Total: ~$700-1,000/month**

---

## 8. Cleanup

To delete all resources:

```bash
# Delete the resource group (removes all resources)
az group delete --name rg-agentchains-dev --yes --no-wait

# Or for production
az group delete --name rg-agentchains-prod --yes --no-wait
```

---

## 9. Troubleshooting

| Issue | Solution |
|-------|----------|
| Deployment fails on PostgreSQL | Ensure the admin password meets complexity requirements (8+ chars, uppercase, lowercase, number) |
| Container App not starting | Check container logs: `az containerapp logs show -g <RG> -n <APP>` |
| Redis connection refused | Verify SSL is enabled and using port 6380 |
| Key Vault access denied | Add your identity to Key Vault access policies |
| OpenAI quota exceeded | Request a quota increase via Azure portal |
| Service Bus not receiving | Check namespace authorization rules and connection string |
