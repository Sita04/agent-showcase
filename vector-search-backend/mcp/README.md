# Vector Search Backend MCP Server

An MCP (Model Context Protocol) server that lets AI agents search a catalog of 2.8M Mercari products using Google Cloud Vector Search 2.0.

## Architecture

```
MCP Client (Claude Code, Gemini CLI, Cursor, ADK Agent, etc.)
    |  stdio (local)
MCP Server (server.py)
    |  HTTPS
Cloud Run REST API
    |  gRPC
Google Cloud Vector Search 2.0 + Gemini + Discovery Engine
```

The server is a thin HTTP proxy — no GCP credentials or heavy dependencies needed locally.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)

That's it. Dependencies (`mcp[cli]`, `httpx`) are declared inline in `server.py` via PEP 723 and installed automatically by `uv` on first run.

## Quick Start

### Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "vector-search-backend": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/vector-search-backend/mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

### Claude Code

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "vector-search-backend": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/vector-search-backend/mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

## Capabilities

### Tools

#### `search_products`

Search the Mercari product catalog using semantic search with reranking.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string (required) | - | Search text (e.g. "vintage leather bag") |
| `dataset_id` | string | `mercari3m_text` | Dataset to search |
| `rows` | int | `10` | Number of results (1-100) |

Returns structured JSON:
```json
{
  "results": [
    {
      "id": "m12345",
      "name": "Vintage Coach Leather Bag",
      "description": "Gently loved vintage Coach bag...",
      "url": "https://www.mercari.com/us/item/m12345/",
      "img_url": "https://u-mercari-images.mercdn.net/photos/m12345_1.jpg",
      "price": 0.0,
      "similarity": 0.5346
    }
  ],
  "count": 10,
  "search_time": "0.45s",
  "index_type": "ANN"
}
```

- `similarity`: rerank score (0–1, higher = more similar). Falls back to dense/sparse distance when reranking is unavailable.
- `price`: placeholder (0.0) — real price data not yet available from the API.

#### `generate_sample_query`

Generate a random search query using Gemini. Useful for demos or exploring the catalog.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dataset_id` | string | `mercari3m_text` | Dataset context |

### Resources

#### `vectorsearch://datasets`

Lists available datasets with metadata (ID, name, description, size, embedding model, dimensions, distance metric, sample queries).

## Available Datasets

| Dataset ID | Embedding Model | Dims | Description |
|---|---|---|---|
| `mercari3m_text` | gemini-embedding-001 | 768 | Full-dimension text embeddings (default) |
| `mercari3m_text_128` | gemini-embedding-001 | 128 | Reduced dimensions, smaller index |
| `mercari3m_text_similarity` | gemini-embedding-001 | 768 | SEMANTIC_SIMILARITY task type |
| `mercari3m_word2vec` | Gensim Word2Vec | 100 | Word-level semantic matching |
| `mercari3m_multimodal` | multimodal-embedding-001 | 1408 | Text-to-image search |

## ADK (Agent Development Kit) Integration

A sample ADK agent is included in `search_agent/`. It uses `McpToolset` to connect to the MCP server and exposes the search tools to a Gemini model.

### Quick Start with adk run

```bash
cd vector-search-backend/mcp
uv run --with google-adk --with mcp adk run search_agent
```

This starts an interactive chat — type a query like "find me vintage leather bags" and press Enter.

### Running with adk web

```bash
cd vector-search-backend/mcp
uv run --with google-adk --with mcp adk web
```

Then open the browser UI and select `search_agent`.

### Agent Code

See `search_agent/agent.py`:

```python
root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="product_search_agent",
    instruction="Help users find products in the Mercari catalog. "
    "Use search_products to search and generate_sample_query for inspiration.",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="uv",
                    args=["run", MCP_SERVER_PATH],
                ),
                timeout=30,
            ),
            tool_filter=["search_products", "generate_sample_query"],
        )
    ],
)
```

### Deployment Note

When deploying ADK agents with MCP tools, the agent and its `McpToolset` must be defined **synchronously** at module level in `agent.py` (not inside an async function). The example above follows this pattern.

## Files

| File | Description |
|---|---|
| `server.py` | MCP server implementation |
| `search_agent/` | Sample ADK agent using this MCP server |
