"""Azure AI Search V2 service — full-text and faceted search for listings, agents, and tools.

Provides both a class-based SearchV2Service for direct use, and module-level async
functions (sync_listings_index, sync_agents_index, sync_tools_index) that accept
a db session and batch-upload records to Azure Search.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful SDK import — falls back to stub if azure-search-documents missing
# ---------------------------------------------------------------------------
try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        ComplexField,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SimpleField,
    )

    _HAS_AZURE_SEARCH = True
except ImportError:
    _HAS_AZURE_SEARCH = False
    logger.warning(
        "azure-search-documents is not installed — SearchV2Service will use stub implementation. "
        "Install with: pip install azure-search-documents"
    )


# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------

def _listings_fields() -> list[dict]:
    """Field schema for the listings index."""
    return [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "title", "type": "Edm.String", "searchable": True},
        {"name": "description", "type": "Edm.String", "searchable": True},
        {"name": "category", "type": "Edm.String", "filterable": True, "facetable": True, "searchable": True},
        {"name": "price_usd", "type": "Edm.Double", "filterable": True, "sortable": True},
        {"name": "seller_id", "type": "Edm.String", "filterable": True},
        {"name": "status", "type": "Edm.String", "filterable": True, "facetable": True},
        {"name": "trust_score", "type": "Edm.Int32", "filterable": True, "sortable": True},
        {"name": "created_at", "type": "Edm.DateTimeOffset", "filterable": True, "sortable": True},
        {"name": "tags", "type": "Collection(Edm.String)", "filterable": True, "facetable": True, "searchable": True},
    ]


def _agents_fields() -> list[dict]:
    """Field schema for the agents index."""
    return [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "name", "type": "Edm.String", "searchable": True},
        {"name": "description", "type": "Edm.String", "searchable": True},
        {"name": "category", "type": "Edm.String", "filterable": True, "facetable": True, "searchable": True},
        {"name": "reputation_score", "type": "Edm.Double", "filterable": True, "sortable": True},
        {"name": "status", "type": "Edm.String", "filterable": True, "facetable": True},
        {"name": "creator_id", "type": "Edm.String", "filterable": True},
        {"name": "total_transactions", "type": "Edm.Int32", "filterable": True, "sortable": True},
        {"name": "created_at", "type": "Edm.DateTimeOffset", "filterable": True, "sortable": True},
    ]


def _tools_fields() -> list[dict]:
    """Field schema for the WebMCP tools index."""
    return [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "name", "type": "Edm.String", "searchable": True},
        {"name": "description", "type": "Edm.String", "searchable": True},
        {"name": "domain", "type": "Edm.String", "filterable": True, "facetable": True, "searchable": True},
        {"name": "category", "type": "Edm.String", "filterable": True, "facetable": True, "searchable": True},
        {"name": "version", "type": "Edm.String", "filterable": True},
        {"name": "status", "type": "Edm.String", "filterable": True, "facetable": True},
        {"name": "execution_count", "type": "Edm.Int32", "filterable": True, "sortable": True},
        {"name": "success_rate", "type": "Edm.Double", "filterable": True, "sortable": True},
        {"name": "creator_id", "type": "Edm.String", "filterable": True},
        {"name": "created_at", "type": "Edm.DateTimeOffset", "filterable": True, "sortable": True},
    ]


# ---------------------------------------------------------------------------
# SearchV2Service
# ---------------------------------------------------------------------------

class SearchV2Service:
    """Azure AI Search integration for the AgentChains marketplace.

    Provides full-text and faceted search across listings, agents, and tools.
    Falls back to a no-op stub when the Azure SDK is not installed.
    """

    def __init__(
        self,
        endpoint: str = "",
        key: str = "",
        index_prefix: str = "agentchains",
    ) -> None:
        self._endpoint = endpoint
        self._key = key
        self._index_prefix = index_prefix

        self._index_client: Any | None = None
        self._search_clients: dict[str, Any] = {}

        if _HAS_AZURE_SEARCH and self._endpoint and self._key:
            self._credential = AzureKeyCredential(self._key)
            self._index_client = SearchIndexClient(
                endpoint=self._endpoint, credential=self._credential
            )
        else:
            self._credential = None
            if self._endpoint and self._key and not _HAS_AZURE_SEARCH:
                logger.warning("Azure AI Search credentials provided but SDK not installed.")
            elif not self._endpoint:
                logger.info("Azure AI Search endpoint not configured — search operates in stub mode.")

    # ----- helpers ----------------------------------------------------------

    def _index_name(self, entity: str) -> str:
        return f"{self._index_prefix}-{entity}"

    def _get_search_client(self, entity: str) -> Any | None:
        """Return a cached SearchClient for the given entity index."""
        if not _HAS_AZURE_SEARCH or not self._credential:
            return None
        name = self._index_name(entity)
        if name not in self._search_clients:
            self._search_clients[name] = SearchClient(
                endpoint=self._endpoint,
                index_name=name,
                credential=self._credential,
            )
        return self._search_clients[name]

    # ----- index management -------------------------------------------------

    def ensure_indexes(self) -> dict[str, bool]:
        """Create indexes for listings, agents, and tools if they don't exist.

        Returns a dict mapping index name to whether it was created (True) or
        already existed (False).
        """
        if not self._index_client:
            logger.info("ensure_indexes: no index client — skipping.")
            return {}

        definitions = {
            "listings": _listings_fields(),
            "agents": _agents_fields(),
            "tools": _tools_fields(),
        }

        existing = {idx.name for idx in self._index_client.list_indexes()}
        results: dict[str, bool] = {}

        for entity, fields in definitions.items():
            idx_name = self._index_name(entity)
            if idx_name in existing:
                results[idx_name] = False
                logger.debug("Index %s already exists — skipping.", idx_name)
                continue

            search_fields = self._build_search_fields(fields)
            index = SearchIndex(name=idx_name, fields=search_fields)
            self._index_client.create_index(index)
            results[idx_name] = True
            logger.info("Created search index: %s", idx_name)

        return results

    @staticmethod
    def _build_search_fields(field_defs: list[dict]) -> list:
        """Convert simple field definition dicts into Azure SearchField objects."""
        if not _HAS_AZURE_SEARCH:
            return []

        type_map = {
            "Edm.String": SearchFieldDataType.String,
            "Edm.Int32": SearchFieldDataType.Int32,
            "Edm.Int64": SearchFieldDataType.Int64,
            "Edm.Double": SearchFieldDataType.Double,
            "Edm.Boolean": SearchFieldDataType.Boolean,
            "Edm.DateTimeOffset": SearchFieldDataType.DateTimeOffset,
            "Collection(Edm.String)": SearchFieldDataType.Collection(SearchFieldDataType.String),
        }

        result = []
        for fd in field_defs:
            ftype = type_map.get(fd["type"], SearchFieldDataType.String)
            is_key = fd.get("key", False)
            searchable = fd.get("searchable", False)
            filterable = fd.get("filterable", False)
            sortable = fd.get("sortable", False)
            facetable = fd.get("facetable", False)

            if searchable:
                field = SearchableField(
                    name=fd["name"],
                    type=ftype,
                    key=is_key,
                    filterable=filterable,
                    sortable=sortable,
                    facetable=facetable,
                )
            else:
                field = SimpleField(
                    name=fd["name"],
                    type=ftype,
                    key=is_key,
                    filterable=filterable,
                    sortable=sortable,
                    facetable=facetable,
                )
            result.append(field)
        return result

    # ----- document indexing -------------------------------------------------

    def index_listing(self, listing_dict: dict) -> bool:
        """Upsert a listing document into the listings index."""
        client = self._get_search_client("listings")
        if not client:
            logger.debug("index_listing: no search client — skipping.")
            return False
        try:
            client.merge_or_upload_documents(documents=[listing_dict])
            return True
        except Exception:
            logger.exception("Failed to index listing %s", listing_dict.get("id"))
            return False

    def index_agent(self, agent_dict: dict) -> bool:
        """Upsert an agent document into the agents index."""
        client = self._get_search_client("agents")
        if not client:
            logger.debug("index_agent: no search client — skipping.")
            return False
        try:
            client.merge_or_upload_documents(documents=[agent_dict])
            return True
        except Exception:
            logger.exception("Failed to index agent %s", agent_dict.get("id"))
            return False

    def index_tool(self, tool_dict: dict) -> bool:
        """Upsert a WebMCP tool document into the tools index."""
        client = self._get_search_client("tools")
        if not client:
            logger.debug("index_tool: no search client — skipping.")
            return False
        try:
            client.merge_or_upload_documents(documents=[tool_dict])
            return True
        except Exception:
            logger.exception("Failed to index tool %s", tool_dict.get("id"))
            return False

    # ----- search -----------------------------------------------------------

    def search_listings(
        self,
        query: str,
        filters: str | None = None,
        facets: list[str] | None = None,
        top: int = 20,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Full-text search over listings with optional OData filter and facets."""
        return self._search(
            entity="listings",
            query=query,
            filters=filters,
            facets=facets or ["category", "status", "tags"],
            top=top,
            skip=skip,
        )

    def search_agents(
        self,
        query: str,
        filters: str | None = None,
        top: int = 20,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Full-text search over agents."""
        return self._search(
            entity="agents",
            query=query,
            filters=filters,
            facets=["category", "status"],
            top=top,
            skip=skip,
        )

    def search_tools(
        self,
        query: str,
        filters: str | None = None,
        top: int = 20,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Full-text search over WebMCP tools."""
        return self._search(
            entity="tools",
            query=query,
            filters=filters,
            facets=["domain", "category", "status"],
            top=top,
            skip=skip,
        )

    def _search(
        self,
        entity: str,
        query: str,
        filters: str | None = None,
        facets: list[str] | None = None,
        top: int = 20,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Internal search helper."""
        client = self._get_search_client(entity)
        if not client:
            return {"results": [], "count": 0, "facets": {}}

        try:
            kwargs: dict[str, Any] = {
                "search_text": query,
                "include_total_count": True,
                "top": top,
                "skip": skip,
            }
            if filters:
                kwargs["filter"] = filters
            if facets:
                kwargs["facets"] = facets

            response = client.search(**kwargs)

            results = []
            for doc in response:
                results.append(dict(doc))

            facet_results: dict[str, list[dict]] = {}
            if hasattr(response, "get_facets") and callable(response.get_facets):
                raw_facets = response.get_facets()
                if raw_facets:
                    for facet_name, facet_values in raw_facets.items():
                        facet_results[facet_name] = [
                            {"value": fv.get("value", ""), "count": fv.get("count", 0)}
                            for fv in facet_values
                        ]

            return {
                "results": results,
                "count": response.get_count() if hasattr(response, "get_count") else len(results),
                "facets": facet_results,
            }
        except Exception:
            logger.exception("Search failed for entity=%s query=%s", entity, query)
            return {"results": [], "count": 0, "facets": {}}

    # ----- delete -----------------------------------------------------------

    def delete_document(self, index_name: str, doc_id: str) -> bool:
        """Delete a document by ID from the specified index."""
        if not _HAS_AZURE_SEARCH or not self._credential:
            logger.debug("delete_document: no client — skipping.")
            return False
        try:
            client = SearchClient(
                endpoint=self._endpoint,
                index_name=index_name,
                credential=self._credential,
            )
            client.delete_documents(documents=[{"id": doc_id}])
            return True
        except Exception:
            logger.exception("Failed to delete document %s from %s", doc_id, index_name)
            return False


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_search_service: SearchV2Service | None = None


def get_search_service() -> SearchV2Service:
    """Return the singleton SearchV2Service, lazily initialised from settings."""
    global _search_service
    if _search_service is None:
        _search_service = SearchV2Service(
            endpoint=settings.azure_search_endpoint,
            key=settings.azure_search_key,
            index_prefix=settings.azure_search_index_prefix,
        )
    return _search_service


# ---------------------------------------------------------------------------
# Async database-backed index sync functions
# ---------------------------------------------------------------------------


async def sync_listings_index(db: AsyncSession) -> dict[str, Any]:
    """Sync active DataListing records from the database to the listings search index."""
    svc = get_search_service()
    client = svc._get_search_client("listings")
    if client is None:
        logger.info("sync_listings_index: no search client — skipping.")
        return {"synced": 0, "status": "skipped"}

    from marketplace.models.listing import DataListing

    result = await db.execute(select(DataListing).where(DataListing.status == "active"))
    listings = list(result.scalars().all())

    documents = []
    for listing in listings:
        tags = []
        if listing.tags:
            try:
                tags = json.loads(listing.tags) if isinstance(listing.tags, str) else listing.tags
            except (json.JSONDecodeError, TypeError):
                tags = []

        documents.append({
            "id": listing.id,
            "title": listing.title,
            "description": listing.description or "",
            "category": listing.category,
            "price_usd": float(listing.price_usdc) if listing.price_usdc else 0,
            "seller_id": listing.seller_id,
            "status": listing.status,
            "trust_score": listing.trust_score or 0,
            "tags": tags,
            "created_at": listing.created_at.isoformat() if listing.created_at else None,
        })

    if documents:
        try:
            client.merge_or_upload_documents(documents=documents)
            logger.info("Synced %d listings to search index", len(documents))
            return {"synced": len(documents), "status": "ok"}
        except Exception as exc:
            logger.error("Failed to sync listings index: %s", exc)
            return {"synced": 0, "error": str(exc), "status": "error"}

    return {"synced": 0, "status": "ok"}


async def sync_agents_index(db: AsyncSession) -> dict[str, Any]:
    """Sync active RegisteredAgent records from the database to the agents search index."""
    svc = get_search_service()
    client = svc._get_search_client("agents")
    if client is None:
        logger.info("sync_agents_index: no search client — skipping.")
        return {"synced": 0, "status": "skipped"}

    from marketplace.models.agent import RegisteredAgent

    result = await db.execute(select(RegisteredAgent).where(RegisteredAgent.status == "active"))
    agents = list(result.scalars().all())

    documents = []
    for agent in agents:
        documents.append({
            "id": agent.id,
            "name": agent.name,
            "description": agent.description or "",
            "category": agent.agent_type,
            "status": agent.status,
            "creator_id": agent.creator_id or "",
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
        })

    if documents:
        try:
            client.merge_or_upload_documents(documents=documents)
            logger.info("Synced %d agents to search index", len(documents))
            return {"synced": len(documents), "status": "ok"}
        except Exception as exc:
            logger.error("Failed to sync agents index: %s", exc)
            return {"synced": 0, "error": str(exc), "status": "error"}

    return {"synced": 0, "status": "ok"}


async def sync_tools_index(db: AsyncSession) -> dict[str, Any]:
    """Sync approved/active WebMCPTool records from the database to the tools search index."""
    svc = get_search_service()
    client = svc._get_search_client("tools")
    if client is None:
        logger.info("sync_tools_index: no search client — skipping.")
        return {"synced": 0, "status": "skipped"}

    from marketplace.models.webmcp_tool import WebMCPTool

    result = await db.execute(
        select(WebMCPTool).where(WebMCPTool.status.in_(["approved", "active"]))
    )
    tools = list(result.scalars().all())

    documents = []
    for tool in tools:
        documents.append({
            "id": tool.id,
            "name": tool.name,
            "description": tool.description or "",
            "domain": tool.domain,
            "category": tool.category,
            "version": tool.version,
            "status": tool.status,
            "execution_count": tool.execution_count or 0,
            "success_rate": float(tool.success_rate) if tool.success_rate else 1.0,
            "creator_id": tool.creator_id,
            "created_at": tool.created_at.isoformat() if tool.created_at else None,
        })

    if documents:
        try:
            client.merge_or_upload_documents(documents=documents)
            logger.info("Synced %d tools to search index", len(documents))
            return {"synced": len(documents), "status": "ok"}
        except Exception as exc:
            logger.error("Failed to sync tools index: %s", exc)
            return {"synced": 0, "error": str(exc), "status": "error"}

    return {"synced": 0, "status": "ok"}
