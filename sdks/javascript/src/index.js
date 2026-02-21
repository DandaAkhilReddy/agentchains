/**
 * AgentChains JavaScript SDK
 * Client library for the AgentChains marketplace API.
 */

export class AgentChainsClient {
  /**
   * @param {Object} options
   * @param {string} [options.baseUrl='http://localhost:8000']
   * @param {string} [options.token]
   * @param {number} [options.timeout=30000]
   */
  constructor({ baseUrl = 'http://localhost:8000', token, timeout = 30000 } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.token = token;
    this.timeout = timeout;
  }

  /** @private */
  async _request(method, path, { body, params } = {}) {
    const url = new URL(path, this.baseUrl);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
    }
    const headers = { 'Content-Type': 'application/json' };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const resp = await fetch(url.toString(), {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text}`);
      }
      return resp.json();
    } finally {
      clearTimeout(timer);
    }
  }

  // Health
  health() { return this._request('GET', '/api/v1/health'); }

  // Agents
  registerAgent(data) { return this._request('POST', '/api/v1/agents', { body: data }); }
  getAgent(agentId) { return this._request('GET', `/api/v1/agents/${agentId}`); }
  listAgents({ skip = 0, limit = 20 } = {}) {
    return this._request('GET', '/api/v1/agents', { params: { skip, limit } });
  }

  // Listings
  createListing(data) { return this._request('POST', '/api/v1/listings', { body: data }); }
  getListing(listingId) { return this._request('GET', `/api/v1/listings/${listingId}`); }
  searchListings({ query = '', skip = 0, limit = 20 } = {}) {
    return this._request('GET', '/api/v1/listings', { params: { q: query, skip, limit } });
  }

  // Transactions
  createTransaction(data) { return this._request('POST', '/api/v1/transactions', { body: data }); }
  getTransaction(txId) { return this._request('GET', `/api/v1/transactions/${txId}`); }

  // Actions
  executeAction(actionId, params = {}) {
    return this._request('POST', `/api/v3/webmcp/actions/${actionId}/execute`, {
      body: { parameters: params },
    });
  }

  // Workflows
  createWorkflow(data) { return this._request('POST', '/api/v3/orchestration/workflows', { body: data }); }
  executeWorkflow(workflowId, inputData = {}) {
    return this._request('POST', `/api/v3/orchestration/workflows/${workflowId}/execute`, {
      body: { input_data: inputData },
    });
  }
}

export default AgentChainsClient;
