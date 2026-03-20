# Vector Search Backend MCP Server

An MCP (Model Context Protocol) server that lets AI agents search a catalog of Mercari products using Google Cloud Vector Search 2.0 with multimodal embeddings.

## Architecture

```
MCP Client (Claude Code, Gemini CLI, Cursor, ADK Agent, etc.)
    |  stdio (local)
MCP Server (server.py)
    |  HTTPS
Cloud Run REST API
    |  gRPC
Google Cloud Vector Search 2.0 + Gemini Embedding 2 + Discovery Engine
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

Search the Mercari product catalog using dual vector search (text + image embeddings) with semantic reranking.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string (required) | - | Search text (e.g. "vintage leather bag") |
| `dataset_id` | string | `mercari1m_mm2` | Dataset to search |
| `rows` | int | `10` | Number of results (1-100) |
| `filter` | string | `""` | JSON metadata filter (see below) |

**Filter examples:**

```
Price under $50:        {"price": {"$lt": 50}}
Price range:            {"$and": [{"price": {"$gte": 10}}, {"price": {"$lte": 50}}]}
```

Supported operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$and`, `$or`.

> **Note:** Filtering requires the target field to be in `filter_fields` on the ANN index. The default dataset (`mercari1m_mm2`) supports price filtering.

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
      "price": 45.0,
      "similarity": 8.1967
    }
  ],
  "count": 10,
  "search_time": "0.04s",
  "index_type": "ANN"
}
```

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `results` | array | List of matching product objects |
| `results[].id` | string | Unique product identifier (e.g. `m12345`) |
| `results[].name` | string | Product title |
| `results[].description` | string | Product description text |
| `results[].url` | string | Mercari product page URL |
| `results[].img_url` | string | Product image URL |
| `results[].price` | float | Estimated price in USD (Gemini-generated). Only present for datasets with `price` in index `store_fields` |
| `results[].similarity` | float | Relevance score. Combined RRF score from dual vector search (text_emb + image_emb) for the default dataset. Falls back to dense or sparse distance for other datasets. Higher is more relevant |
| `count` | int | Number of results returned |
| `search_time` | string | Backend query latency (e.g. `"0.04s"`) |
| `index_type` | string | `"ANN"` (approximate nearest neighbor index) or `"kNN"` (brute-force scan) or `"N/A"` |

#### `generate_sample_query`

Generate a random search query using Gemini. Useful for demos or exploring the catalog.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dataset_id` | string | `mercari1m_mm2` | Dataset context |

### Resources

#### `vectorsearch://datasets`

Lists available datasets with metadata (ID, name, description, size, embedding model, dimensions, distance metric, sample queries).

## Available Datasets

| Dataset ID | Embedding Model | Dims | Items | Description |
|---|---|---|---|---|
| `mercari1m_mm2` | gemini-embedding-2-preview | 768 | 882K | Dual vector (text+image) multimodal search **(default)** |
| `mercari3m_text` | gemini-embedding-001 | 768 | 2.8M | Full-dimension text embeddings |
| `mercari3m_text_128` | gemini-embedding-001 | 128 | 2.8M | Reduced dimensions, smaller index |
| `mercari3m_text_similarity` | gemini-embedding-001 | 768 | 2.8M | SEMANTIC_SIMILARITY task type |
| `mercari3m_word2vec` | Gensim Word2Vec | 100 | 2.8M | Word-level semantic matching |
| `mercari3m_multimodal` | multimodal-embedding-001 | 1408 | 2.8M | Text-to-image search |

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
