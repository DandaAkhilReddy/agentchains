#!/usr/bin/env bash
# =============================================================================
# Azure Deployment Script — Indian Loan Analyzer
# =============================================================================
# Provisions all Azure resources and deploys the application containers.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Docker installed and running
#   - A .env file at the project root with all required secrets
#
# Usage:
#   chmod +x infra/azure-deploy.sh
#   ./infra/azure-deploy.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Parameters — customize these for your deployment
# ---------------------------------------------------------------------------
RESOURCE_GROUP="rg-loan-analyzer"
LOCATION="centralindia"
ACR_NAME="loanalyzeracr"          # Must be globally unique, lowercase alphanumeric
DB_SERVER_NAME="loan-analyzer-db"  # Must be globally unique
DB_ADMIN_USER="pgadmin"
DB_ADMIN_PASSWORD=""               # Set via environment or prompt below
DB_NAME="loan_analyzer"
APP_PLAN_NAME="plan-loan-analyzer"
APP_PLAN_SKU="B1"
BACKEND_APP_NAME="app-loan-analyzer-api"    # Must be globally unique
FRONTEND_APP_NAME="app-loan-analyzer-web"   # Must be globally unique

# ---------------------------------------------------------------------------
# Prompt for database password if not set
# ---------------------------------------------------------------------------
if [ -z "${DB_ADMIN_PASSWORD}" ]; then
    read -rsp "Enter PostgreSQL admin password: " DB_ADMIN_PASSWORD
    echo
fi

echo "==> Starting Azure deployment for Indian Loan Analyzer"
echo "    Resource Group : ${RESOURCE_GROUP}"
echo "    Location       : ${LOCATION}"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Create Resource Group
# ---------------------------------------------------------------------------
echo "==> [1/8] Creating resource group '${RESOURCE_GROUP}' in '${LOCATION}'..."
az group create \
    --name "${RESOURCE_GROUP}" \
    --location "${LOCATION}" \
    --output none

# ---------------------------------------------------------------------------
# Step 2: Create Azure Container Registry
# ---------------------------------------------------------------------------
echo "==> [2/8] Creating Azure Container Registry '${ACR_NAME}'..."
az acr create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${ACR_NAME}" \
    --sku Basic \
    --admin-enabled true \
    --output none

# Get ACR credentials for later use
ACR_LOGIN_SERVER=$(az acr show --name "${ACR_NAME}" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "${ACR_NAME}" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "${ACR_NAME}" --query "passwords[0].value" -o tsv)

echo "    ACR Login Server: ${ACR_LOGIN_SERVER}"

# ---------------------------------------------------------------------------
# Step 3: Create Azure Database for PostgreSQL Flexible Server
# ---------------------------------------------------------------------------
echo "==> [3/8] Creating PostgreSQL Flexible Server '${DB_SERVER_NAME}'..."
az postgres flexible-server create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${DB_SERVER_NAME}" \
    --location "${LOCATION}" \
    --admin-user "${DB_ADMIN_USER}" \
    --admin-password "${DB_ADMIN_PASSWORD}" \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --version 16 \
    --yes \
    --output none

# Create the application database
echo "    Creating database '${DB_NAME}'..."
az postgres flexible-server db create \
    --resource-group "${RESOURCE_GROUP}" \
    --server-name "${DB_SERVER_NAME}" \
    --database-name "${DB_NAME}" \
    --output none

# Enable the pgvector extension
echo "    Enabling pgvector extension..."
az postgres flexible-server parameter set \
    --resource-group "${RESOURCE_GROUP}" \
    --server-name "${DB_SERVER_NAME}" \
    --name azure.extensions \
    --value VECTOR \
    --output none

# Allow Azure services to connect
echo "    Configuring firewall for Azure services..."
az postgres flexible-server firewall-rule create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${DB_SERVER_NAME}" \
    --rule-name AllowAzureServices \
    --start-ip-address 0.0.0.0 \
    --end-ip-address 0.0.0.0 \
    --output none

DB_HOST="${DB_SERVER_NAME}.postgres.database.azure.com"
DATABASE_URL="postgresql+asyncpg://${DB_ADMIN_USER}:${DB_ADMIN_PASSWORD}@${DB_HOST}:5432/${DB_NAME}?sslmode=require"

# ---------------------------------------------------------------------------
# Step 4: Create App Service Plan (Linux, B1)
# ---------------------------------------------------------------------------
echo "==> [4/8] Creating App Service Plan '${APP_PLAN_NAME}' (${APP_PLAN_SKU})..."
az appservice plan create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${APP_PLAN_NAME}" \
    --sku "${APP_PLAN_SKU}" \
    --is-linux \
    --output none

# ---------------------------------------------------------------------------
# Step 5: Create Web App for Backend (container)
# ---------------------------------------------------------------------------
echo "==> [5/8] Creating backend Web App '${BACKEND_APP_NAME}'..."
az webapp create \
    --resource-group "${RESOURCE_GROUP}" \
    --plan "${APP_PLAN_NAME}" \
    --name "${BACKEND_APP_NAME}" \
    --container-image-name "${ACR_LOGIN_SERVER}/loan-analyzer-backend:latest" \
    --container-registry-url "https://${ACR_LOGIN_SERVER}" \
    --container-registry-user "${ACR_USERNAME}" \
    --container-registry-password "${ACR_PASSWORD}" \
    --output none

# ---------------------------------------------------------------------------
# Step 6: Create Web App for Frontend (container)
# ---------------------------------------------------------------------------
echo "==> [6/8] Creating frontend Web App '${FRONTEND_APP_NAME}'..."
az webapp create \
    --resource-group "${RESOURCE_GROUP}" \
    --plan "${APP_PLAN_NAME}" \
    --name "${FRONTEND_APP_NAME}" \
    --container-image-name "${ACR_LOGIN_SERVER}/loan-analyzer-frontend:latest" \
    --container-registry-url "https://${ACR_LOGIN_SERVER}" \
    --container-registry-user "${ACR_USERNAME}" \
    --container-registry-password "${ACR_PASSWORD}" \
    --output none

# ---------------------------------------------------------------------------
# Step 7: Configure Environment Variables
# ---------------------------------------------------------------------------
echo "==> [7/8] Configuring environment variables..."

# Backend environment variables
# Note: Add your actual Azure service keys here or set them manually in the portal
FRONTEND_URL="https://${FRONTEND_APP_NAME}.azurewebsites.net"
BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"

az webapp config appsettings set \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${BACKEND_APP_NAME}" \
    --settings \
        DATABASE_URL="${DATABASE_URL}" \
        ENVIRONMENT="production" \
        LOG_LEVEL="INFO" \
        WEBSITES_PORT="8000" \
        CORS_ORIGINS="${FRONTEND_URL}" \
    --output none

# Frontend runtime env var — nginx proxy target
az webapp config appsettings set \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FRONTEND_APP_NAME}" \
    --settings \
        BACKEND_URL="${BACKEND_URL}" \
        WEBSITES_PORT="80" \
    --output none

echo "    Backend env vars configured."
echo "    NOTE: You must manually set these secrets in the Azure Portal or via CLI:"
echo "      - AZURE_OPENAI_ENDPOINT"
echo "      - AZURE_OPENAI_KEY"
echo "      - AZURE_OPENAI_DEPLOYMENT"
echo "      - AZURE_DOC_INTEL_ENDPOINT"
echo "      - AZURE_DOC_INTEL_KEY"
echo "      - AZURE_STORAGE_CONNECTION_STRING"
echo "      - AZURE_TRANSLATOR_KEY"
echo "      - AZURE_TTS_KEY"
echo "      - FIREBASE_PROJECT_ID"

echo "    Frontend URL: ${FRONTEND_URL}"
echo "    Backend URL: ${BACKEND_URL}"

# ---------------------------------------------------------------------------
# Step 8: Build and Push Docker Images
# ---------------------------------------------------------------------------
echo "==> [8/8] Building and pushing Docker images..."

# Log in to ACR
az acr login --name "${ACR_NAME}"

# Build and push backend
echo "    Building backend image..."
docker build -t "${ACR_LOGIN_SERVER}/loan-analyzer-backend:latest" ./backend
docker push "${ACR_LOGIN_SERVER}/loan-analyzer-backend:latest"

# Build and push frontend (with build-time args)
echo "    Building frontend image..."
docker build \
    --build-arg VITE_API_BASE_URL="${BACKEND_URL}" \
    -t "${ACR_LOGIN_SERVER}/loan-analyzer-frontend:latest" \
    ./frontend
docker push "${ACR_LOGIN_SERVER}/loan-analyzer-frontend:latest"

# Restart apps to pick up new images
echo "    Restarting web apps..."
az webapp restart --resource-group "${RESOURCE_GROUP}" --name "${BACKEND_APP_NAME}"
az webapp restart --resource-group "${RESOURCE_GROUP}" --name "${FRONTEND_APP_NAME}"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "=========================================="
echo " Deployment complete!"
echo "=========================================="
echo ""
echo " Backend  : https://${BACKEND_APP_NAME}.azurewebsites.net"
echo " Frontend : https://${FRONTEND_APP_NAME}.azurewebsites.net"
echo ""
echo " Next steps:"
echo "   1. Set remaining secrets in Azure Portal (see list above)"
echo "   2. Run database migrations: az webapp ssh --name ${BACKEND_APP_NAME}"
echo "      then: alembic upgrade head"
echo "   3. Configure custom domain and SSL if needed"
echo "   4. Set up CI/CD in GitHub Actions to auto-deploy on push"
echo ""
