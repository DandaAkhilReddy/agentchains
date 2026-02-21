# A2UI Developer Guide

Build interactive agent-to-user interfaces using the A2UI protocol.

---

## 1. Getting Started

### Prerequisites

- AgentChains platform running (local or deployed)
- A registered agent with a valid JWT token
- WebSocket client (browser, Python, or Node.js)

### Architecture Overview

```
Your Agent Code
     |
     v
A2UI Service (Python)          <-- Push UI components
     |
     v
WebSocket /ws/v4/a2ui          <-- Real-time transport
     |
     v
Browser / Client App           <-- Renders components
     |
     v
User Interaction                <-- Input & approvals flow back
```

A2UI follows a push model: your agent pushes UI components to the user, and the user responds to input and confirmation requests. The agent never needs to poll -- responses arrive as resolved `asyncio.Future` objects.

---

## 2. Python: Pushing UI Components

### 2.1 Import the A2UI Service

```python
from marketplace.services.a2ui_service import (
    push_render,
    push_update,
    request_input,
    request_confirm,
    push_progress,
    push_navigate,
    push_notify,
)
```

### 2.2 Render a Card

```python
component_id = await push_render(
    session_id="your-session-id",
    component_type="card",
    data={
        "title": "Market Analysis",
        "description": "Top trending datasets this week.",
        "sections": [
            {"label": "Most Popular", "value": "ImageNet-2026"},
            {"label": "Fastest Growing", "value": "CodeBench-v3"},
        ],
    },
    metadata={"priority": "high", "position": "main"},
)
print(f"Rendered card: {component_id}")
```

### 2.3 Render a Table

```python
await push_render(
    session_id=session_id,
    component_type="table",
    data={
        "headers": [
            {"key": "name", "label": "Agent", "sortable": True},
            {"key": "calls", "label": "API Calls", "sortable": True},
            {"key": "revenue", "label": "Revenue"},
        ],
        "rows": [
            {"name": "DataBot", "calls": 12400, "revenue": "$62.00"},
            {"name": "ResearchAI", "calls": 8750, "revenue": "$43.75"},
            {"name": "PriceTracker", "calls": 5200, "revenue": "$26.00"},
        ],
    },
)
```

### 2.4 Request User Input

```python
# Ask the user a question and wait for their response
user_query = await request_input(
    session_id=session_id,
    input_type="text",
    prompt="What topic would you like to research?",
    timeout=60,  # seconds
)
print(f"User wants to research: {user_query}")
```

### 2.5 Request User Input with Options

```python
selected_plan = await request_input(
    session_id=session_id,
    input_type="select",
    prompt="Choose a subscription plan:",
    options=["Free", "Pro ($29/mo)", "Enterprise ($99/mo)"],
    timeout=120,
)
```

### 2.6 Request Confirmation

```python
result = await request_confirm(
    session_id=session_id,
    title="Confirm Purchase",
    description="This will charge $25.00 to your account for 'NLP-Commons' dataset.",
    severity="warning",
    timeout=30,
)

if result["approved"]:
    # Process the purchase
    await push_notify(session_id, "success", "Purchase Complete", "Dataset access granted.")
else:
    await push_notify(session_id, "info", "Cancelled", result.get("reason", "User declined."))
```

### 2.7 Stream Progress

```python
import asyncio

task_id = "analysis-task-001"

for step in range(1, 6):
    await push_progress(
        session_id=session_id,
        task_id=task_id,
        progress_type="determinate",
        value=step * 20,
        total=100,
        message=f"Processing step {step} of 5...",
    )
    await asyncio.sleep(2)  # Simulate work

await push_notify(session_id, "success", "Analysis Complete")
```

### 2.8 Update an Existing Component

```python
# First, render a component
cid = await push_render(
    session_id=session_id,
    component_type="markdown",
    data={"content": "## Loading results..."},
)

# Later, update it in place
await push_update(
    session_id=session_id,
    component_id=cid,
    operation="replace",
    data={"content": "## Results\n\nFound **42** matching datasets."},
)
```

### 2.9 Navigate and Notify

```python
# Send a toast notification
await push_notify(
    session_id=session_id,
    level="info",
    title="New Opportunity",
    message="A demand spike was detected in the 'finance' category.",
    duration_ms=8000,
)

# Redirect the user
await push_navigate(
    session_id=session_id,
    url="/marketplace/finance",
    new_tab=False,
)
```

---

## 3. JavaScript Client Usage

### 3.1 Connecting to A2UI

```javascript
// Step 1: Obtain a stream token
const tokenResponse = await fetch('/api/v4/stream-token', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${agentToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ token_type: 'stream_a2ui' }),
});
const { token } = await tokenResponse.json();

// Step 2: Connect via WebSocket
const ws = new WebSocket(`wss://${location.host}/ws/v4/a2ui?token=${token}`);

ws.onopen = () => {
  // Step 3: Initialize the session
  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'a2ui.init',
    id: '1',
    params: {
      client_info: {
        name: 'MyApp',
        version: '1.0.0',
        viewport: { width: window.innerWidth, height: window.innerHeight },
      },
      capabilities: {
        supported_components: ['card', 'table', 'form', 'chart', 'markdown', 'code', 'image', 'alert', 'steps'],
        max_concurrent_components: 20,
        supports_file_upload: false,
      },
    },
  }));
};
```

### 3.2 Handling Messages

```javascript
let sessionId = null;

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  // Handle init response
  if (msg.id === '1' && msg.result) {
    sessionId = msg.result.session_id;
    console.log('Session initialized:', sessionId);
    return;
  }

  // Handle agent-to-UI notifications
  switch (msg.method) {
    case 'ui.render':
      renderComponent(msg.params);
      break;

    case 'ui.update':
      updateComponent(msg.params);
      break;

    case 'ui.request_input':
      showInputDialog(msg.params);
      break;

    case 'ui.confirm':
      showConfirmDialog(msg.params);
      break;

    case 'ui.progress':
      updateProgress(msg.params);
      break;

    case 'ui.navigate':
      handleNavigation(msg.params);
      break;

    case 'ui.notify':
      showToast(msg.params);
      break;
  }
};
```

### 3.3 Responding to Requests

```javascript
function showInputDialog(params) {
  const { request_id, input_type, prompt, options } = params;

  // Show your UI input dialog...
  // When user submits:
  const userValue = getUserInput(); // your UI logic

  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'user.respond',
    params: {
      request_id: request_id,
      value: userValue,
    },
  }));
}

function showConfirmDialog(params) {
  const { request_id, title, description, severity } = params;

  // Show your confirmation dialog...
  // When user decides:
  const approved = getUserDecision(); // your UI logic

  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'user.approve',
    params: {
      request_id: request_id,
      approved: approved,
      reason: approved ? null : 'User declined',
    },
  }));
}
```

### 3.4 Cancelling Operations

```javascript
function cancelTask(taskId) {
  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'user.cancel',
    params: {
      task_id: taskId,
      reason: 'User requested cancellation',
    },
  }));
}
```

---

## 4. Building Custom Widgets

### 4.1 Component Renderer Pattern

Create a component registry that maps `component_type` to render functions:

```javascript
const componentRenderers = {
  card: renderCard,
  table: renderTable,
  form: renderForm,
  chart: renderChart,
  markdown: renderMarkdown,
  code: renderCode,
  image: renderImage,
  alert: renderAlert,
  steps: renderSteps,
};

function renderComponent(params) {
  const { component_id, component_type, data, metadata } = params;
  const renderer = componentRenderers[component_type];

  if (!renderer) {
    console.warn(`Unknown component type: ${component_type}`);
    return;
  }

  const element = renderer(data, metadata);
  element.dataset.componentId = component_id;
  document.getElementById('a2ui-container').appendChild(element);
}
```

### 4.2 React Component Example

```tsx
import React, { useEffect, useState } from 'react';

interface A2UIComponent {
  component_id: string;
  component_type: string;
  data: Record<string, any>;
  metadata?: Record<string, any>;
}

function A2UIContainer({ sessionId }: { sessionId: string }) {
  const [components, setComponents] = useState<A2UIComponent[]>([]);

  // Handle ui.render messages
  const handleRender = (params: A2UIComponent) => {
    setComponents(prev => [...prev, params]);
  };

  // Handle ui.update messages
  const handleUpdate = (params: { component_id: string; operation: string; data: any }) => {
    setComponents(prev =>
      prev.map(comp =>
        comp.component_id === params.component_id
          ? { ...comp, data: params.operation === 'replace' ? params.data : { ...comp.data, ...params.data } }
          : comp
      )
    );
  };

  return (
    <div className="a2ui-container">
      {components.map(comp => (
        <A2UIWidget key={comp.component_id} {...comp} />
      ))}
    </div>
  );
}

function A2UIWidget({ component_type, data }: A2UIComponent) {
  switch (component_type) {
    case 'card':
      return <CardWidget data={data} />;
    case 'table':
      return <TableWidget data={data} />;
    case 'markdown':
      return <MarkdownWidget data={data} />;
    // ... add more component types
    default:
      return <div>Unknown component: {component_type}</div>;
  }
}
```

### 4.3 Registering Custom Component Types

If you need to extend A2UI with custom component types beyond the standard 9, use the `metadata` field to pass rendering hints:

```python
await push_render(
    session_id=session_id,
    component_type="card",  # Use a standard type as base
    data={
        "title": "Custom Widget",
        "content": {
            "widget_type": "price_ticker",
            "symbol": "ETH/USD",
            "price": 3250.00,
            "change_pct": 2.4,
        },
    },
    metadata={
        "custom_renderer": "price_ticker",
        "refresh_interval_ms": 5000,
    },
)
```

On the client side, check `metadata.custom_renderer` to select a specialized renderer.

---

## 5. Best Practices

### 5.1 Performance

- **Batch updates**: Use `ui.update` with `merge` instead of re-rendering entire components.
- **Limit concurrent components**: Remove stale components before rendering new ones. The recommended maximum is 20 concurrent components per session.
- **Use progress indicators**: For operations taking more than 2 seconds, always send `ui.progress` updates to keep the user informed.
- **Set timeouts**: Always specify `timeout` on `request_input` and `request_confirm` calls to prevent indefinite blocking.

### 5.2 Security

- **Never trust client input**: Validate all values returned via `user.respond` on the server side.
- **Use severity levels**: For destructive actions (purchases, deletions), always use `severity: "critical"` in confirmation requests.
- **Respect consent**: Check consent status before collecting or displaying sensitive data.
- **Do not embed secrets**: Never include API keys, tokens, or credentials in component data.

### 5.3 User Experience

- **Progressive disclosure**: Start with summary cards, then reveal details on user interaction.
- **Provide context**: Always include a descriptive `prompt` with input requests and `description` with confirmations.
- **Handle errors gracefully**: Use `ui.notify` with `level: "error"` to communicate failures, and always offer a recovery path.
- **Use appropriate component types**: Tables for structured data, charts for trends, markdown for rich text, alerts for important messages.
- **Toast duration**: Use 3000ms for success messages, 5000ms for info, and 8000ms+ for warnings/errors.

### 5.4 Error Handling

```python
import asyncio

try:
    user_value = await request_input(
        session_id=session_id,
        input_type="text",
        prompt="Enter your search query:",
        timeout=60,
    )
except asyncio.TimeoutError:
    await push_notify(
        session_id=session_id,
        level="warning",
        title="Input Timeout",
        message="No response received. Please try again.",
    )
except ValueError as e:
    await push_notify(
        session_id=session_id,
        level="error",
        title="Error",
        message=str(e),
    )
```

### 5.5 Session Management

- Always handle WebSocket disconnections gracefully in your client code.
- Implement reconnection logic with exponential backoff.
- Re-initialize the session (`a2ui.init`) after reconnecting.
- Do not assume component state persists across reconnections -- re-render as needed.
