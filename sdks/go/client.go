// Package agentchains provides a Go client for the AgentChains marketplace API.
package agentchains

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client is the AgentChains API client.
type Client struct {
	BaseURL    string
	Token      string
	HTTPClient *http.Client
}

// NewClient creates a new AgentChains client.
func NewClient(baseURL string, token string) *Client {
	return &Client{
		BaseURL: baseURL,
		Token:   token,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *Client) doRequest(ctx context.Context, method, path string, body interface{}) (map[string]interface{}, error) {
	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("marshal body: %w", err)
		}
		reqBody = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, reqBody)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(respBody))
	}

	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}
	return result, nil
}

// Health checks the API health.
func (c *Client) Health(ctx context.Context) (map[string]interface{}, error) {
	return c.doRequest(ctx, http.MethodGet, "/api/v1/health", nil)
}

// RegisterAgent registers a new agent.
func (c *Client) RegisterAgent(ctx context.Context, data map[string]interface{}) (map[string]interface{}, error) {
	return c.doRequest(ctx, http.MethodPost, "/api/v1/agents", data)
}

// GetAgent gets an agent by ID.
func (c *Client) GetAgent(ctx context.Context, agentID string) (map[string]interface{}, error) {
	return c.doRequest(ctx, http.MethodGet, "/api/v1/agents/"+agentID, nil)
}

// CreateListing creates a new listing.
func (c *Client) CreateListing(ctx context.Context, data map[string]interface{}) (map[string]interface{}, error) {
	return c.doRequest(ctx, http.MethodPost, "/api/v1/listings", data)
}

// CreateTransaction creates a new transaction.
func (c *Client) CreateTransaction(ctx context.Context, data map[string]interface{}) (map[string]interface{}, error) {
	return c.doRequest(ctx, http.MethodPost, "/api/v1/transactions", data)
}

// ExecuteWorkflow executes a workflow.
func (c *Client) ExecuteWorkflow(ctx context.Context, workflowID string, inputData map[string]interface{}) (map[string]interface{}, error) {
	body := map[string]interface{}{"input_data": inputData}
	return c.doRequest(ctx, http.MethodPost, "/api/v3/orchestration/workflows/"+workflowID+"/execute", body)
}
