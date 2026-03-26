# Vector Search Backend API Specification

**Base URL**: [`https://ac-web2-761793285222.us-central1.run.app`](https://ac-web2-761793285222.us-central1.run.app)

A Flask-based search backend powered by Google Cloud Vertex AI Vector Search 2.0. Provides semantic, text, and hybrid search over product datasets (~2.8M Mercari items). CORS is enabled for all origins. An [MCP server](#mcp-server) is also available for AI agent integration.

> **Important:** The product dataset is provided courtesy of [Mercari, Inc.](https://www.mercari.com/). Any demo or UI built on this API must display an attribution such as "Product data provided courtesy of [Mercari](https://www.mercari.com/)".

---

## Endpoints

### 1. `POST /api/query` — Search Products

The main search endpoint. Supports semantic search (dense vector embeddings), text search (keyword matching), and hybrid search (both combined with Reciprocal Rank Fusion).

Also supports `GET` with query parameters.

#### Search Request Body (JSON)

| Field | Type | Required | Default | Description |
| ------- | ------ | ---------- | --------- | ------------- |
| `query` | string | Yes | — | Search query text (min 1 character) |
| `rows` | integer | No | `50` | Number of results to return (1–1000) |
| `dataset_id` | string | No | `"mercari3m_text_128"` | Dataset to search (see [Datasets](#datasets)) |
| `use_semantic_search` | boolean | No | `true` | Enable semantic (vector) search |
| `use_text_search` | boolean | No | `false` | Enable keyword text search. **Note:** currently only supports exact matching |
| `rrf_alpha` | float | No | `0.5` | RRF weight for semantic search (0–1). Text search weight = 1 − rrf_alpha. Only applies to hybrid search |
| `use_rerank` | string | No | `null` | Set to `"ranking_api"` to enable Discovery Engine reranking |
| `force_knn` | boolean | No | `null` | `true` = force brute-force kNN, `false` = force ANN index, `null` = auto |

**Validation rules:**

- At least one of `use_semantic_search` or `use_text_search` must be `true`
- `rrf_alpha` must be between 0 and 1
- `dataset_id` must be a valid dataset ID if provided

#### Search Modes

| `use_semantic_search` | `use_text_search` | Mode |
| --- | --- | --- |
| `true` | `false` | **Semantic search** — dense vector similarity using Gemini embeddings |
| `false` | `true` | **Text search** — keyword matching on `name` and `description` fields |
| `true` | `true` | **Hybrid search** — semantic + text combined with RRF ranking |

#### Example Request

```json
{
  "query": "vintage leather jacket",
  "rows": 20,
  "use_semantic_search": true,
  "use_text_search": true,
  "rrf_alpha": 0.6,
  "use_rerank": "ranking_api"
}
```

#### Example Search GET Request

```bash
GET /api/query?query=vintage+leather+jacket&rows=20&use_semantic_search=true&use_text_search=true&rrf_alpha=0.6
```

#### Search Response (200 OK)

```json
{
  "items": [
    {
      "id": "m54255895141",
      "name": "Vintage Brown Leather Jacket",
      "description": "Genuine leather, size M, great condition",
      "img_url": "https://...",
      "url": "https://...",
      "dense_dist": 0.82,
      "sparse_dist": 0.0,
      "rerank_score": 0.0
    }
  ],
  "latencies": {
    "gen_query_emb": 0.0,
    "query": 0.234,
    "rerank": 0.156
  },
  "used_knn": false
}
```

#### Response Fields

| Field | Type | Description |
| ------- | ------ | ------------- |
| `items` | array | List of search result items |
| `items[].id` | string | Item ID (extracted from data object resource name) |
| `items[].name` | string | Product name |
| `items[].description` | string | Product description |
| `items[].img_url` | string | Product image URL |
| `items[].url` | string | Product listing URL. **Note:** as the dataset is not the latest, most product pages will show "sold out" |
| `items[].dense_dist` | float | Semantic search distance score. For hybrid, RRF score × 1000 |
| `items[].sparse_dist` | float | Text search distance score. For hybrid, RRF score × 1000 |
| `items[].rerank_score` | float | Reranking score (0.0 if reranking not used) |
| `latencies` | object | Latency breakdown in seconds |
| `latencies.gen_query_emb` | float | Embedding generation time (non-zero only for BYOE datasets) |
| `latencies.query` | float | Search query execution time |
| `latencies.rerank` | float | Reranking time (0.0 if not used) |
| `used_knn` | boolean or null | `true` = brute-force kNN was used, `false` = ANN index was used, `null` = not applicable (text search only) |

#### Error Response (400 Bad Request)

Returned when request validation fails (missing query, invalid rrf_alpha, unknown dataset, etc.).

```json
{
  "error": "Validation error",
  "details": [
    {
      "loc": ["query"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

### 2. `GET /api/datasets` — List Available Datasets

Returns metadata for all available datasets. Also supports `POST`.

#### Datasets Response (200 OK)

```json
[
  {
    "dataset_id": "mercari3m_text_128",
    "dataset_name": "Mercari 3M items (128-dim Gemini text embeddings)",
    "dataset_desc": "Reduced dimensions for smaller index size...",
    "dataset_url": "https://www.mercari.com/",
    "collection_id": "mercari3m-collection-128",
    "dataset_size": 2874425,
    "item_id": "id",
    "item_name": "name",
    "item_description": "description",
    "item_img_url": "img_url",
    "item_url": "url",
    "sample_query": "Ex. cups, shoes, tables",
    "is_byoe": false,
    "emb_model": "gemini-embedding-001",
    "emb_dims": 128,
    "emb_task_type": "RETRIEVAL_DOCUMENT",
    "emb_source": "{name} {description}",
    "distance_metric": "DOT_PRODUCT",
    "index_id": "name-embedding-index"
  }
]
```

#### Dataset Fields

| Field | Type | Description |
| ------- | ------ | ------------- |
| `dataset_id` | string | Unique identifier for the dataset |
| `dataset_name` | string | Human-readable dataset name |
| `dataset_desc` | string | Description of the dataset and embedding strategy |
| `dataset_url` | string | Source data URL |
| `collection_id` | string | Vector Search 2.0 collection ID |
| `dataset_size` | integer | Number of items in the dataset |
| `item_id`, `item_name`, `item_description`, `item_img_url`, `item_url` | string | Field name mappings for result display |
| `sample_query` | string | Example search query hint |
| `is_byoe` | boolean | `true` if dataset uses Bring Your Own Embeddings (no auto-embeddings) |
| `emb_model` | string | Embedding model used |
| `emb_dims` | integer | Embedding dimensions |
| `emb_task_type` | string | Embedding task type used during indexing |
| `emb_source` | string | Text template or source used for embedding generation |
| `distance_metric` | string | ANN index distance metric (`DOT_PRODUCT` or `COSINE`) |
| `index_id` | string | ANN index identifier |

---

### 3. `POST /api/generate_query` — Generate Sample Query

Uses Gemini to generate a random sample search query appropriate for the dataset. Tracks past queries per session to avoid duplicates. Also supports `GET`.

#### Generate Request Body (JSON)

| Field | Type | Required | Default | Description |
| ------- | ------ | ---------- | --------- | ------------- |
| `dataset_id` | string | No | `"mercari3m_text_128"` | Dataset ID to generate a query for |

#### Example Generate GET Request

```bash
GET /api/generate_query?dataset_id=mercari3m_text_128
```

#### Generate Response (200 OK)

Returns a plain text string (not JSON) with the generated query.

```bash
vintage ceramic coffee mugs
```

---

## Datasets

Each dataset is indexed with a specific embedding task type, which determines the default query task type used at search time:

- **`RETRIEVAL_DOCUMENT`** datasets: queries default to `RETRIEVAL_QUERY` (asymmetric query-document matching)
- **`SEMANTIC_SIMILARITY`** datasets: queries default to `SEMANTIC_SIMILARITY` (symmetric similarity matching)
- **BYOE** datasets: task type is not applicable — embeddings are generated by external models (Word2Vec, multimodal-embedding-001)

| Dataset ID | Embedding Model | Dims | Distance Metric | BYOE | Index Task Type | Query Task Type | Items | Description |
| ------------ | ---------------- | ------ | ----------------- | ------ | ----------------- | ----------------- | ----- | ------------- |
| `mercari1m_mm2` | gemini-embedding-2-preview | 768 | DOT_PRODUCT | No | N/A | N/A | 882K | Dual vector (text+image) multimodal search with Gemini-estimated `price` field and price filtering. MCP server default |
| `mercari3m_text_128` | gemini-embedding-001 | 128 | DOT_PRODUCT | No | RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | 2.8M | REST API default. Reduced-dimension Gemini embeddings |
| `mercari3m_text` | gemini-embedding-001 | 768 | DOT_PRODUCT | No | RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | 2.8M | Full-dimension Gemini embeddings |
| `mercari3m_text_similarity` | gemini-embedding-001 | 768 | DOT_PRODUCT | No | SEMANTIC_SIMILARITY | SEMANTIC_SIMILARITY | 2.8M | Symmetric matching for "find similar items" use cases |
| `mercari3m_word2vec` | Gensim Word2Vec | 100 | COSINE | Yes | N/A | N/A | 2.8M | Word2Vec BYOE — fastest inference, word-level semantics |
| `mercari3m_multimodal` | multimodal-embedding-001 | 1408 | DOT_PRODUCT | Yes | N/A | N/A | 2.8M | Multimodal embeddings encoding item images |

The `mercari3m_*` datasets contain ~2,874,425 Mercari product listings. The `mercari1m_mm2` dataset contains ~882K items with dual text+image embeddings. All datasets include fields: `name`, `description`, `img_url`, `url`.

---

## Notes

- **CORS**: All origins are allowed.
- **BYOE datasets** (`mercari3m_word2vec`, `mercari3m_multimodal`): Semantic search generates query embeddings at search time (Word2Vec or multimodal-embedding-001). The `latencies.gen_query_emb` field reflects this cost. Text search works the same as auto-embedding datasets.
- **Reranking**: When `use_rerank=ranking_api` is set, results are reranked using the Discovery Engine Ranking API (`semantic-ranker-512@latest`). The `rerank_score` field is populated and item order reflects the reranked order.
- **Session**: The service assigns a session ID via cookies. The `/api/generate_query` endpoint uses this to avoid repeating previously generated queries.

---

## MCP Server

An MCP (Model Context Protocol) server in [`mcp/`](mcp/) lets AI agents use the search backend via stdio. It is a thin HTTP proxy — no GCP credentials or heavy dependencies needed locally.

```
MCP Client (Claude Code, Gemini CLI, Cursor, ADK Agent, etc.)
    |  stdio (local)
MCP Server (mcp/server.py)
    |  HTTPS
Cloud Run REST API
    |  gRPC
Google Cloud Vector Search 2.0 + Gemini Embedding 2 + Discovery Engine
```

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)

Dependencies (`mcp[cli]`, `httpx`) are declared inline in `server.py` via PEP 723 and installed automatically by `uv` on first run.

### Client Configuration

#### Gemini CLI

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

#### Claude Code

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

### MCP Tools

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

### MCP Resources

#### `vectorsearch://datasets`

Lists available datasets with metadata (ID, name, description, size, embedding model, dimensions, distance metric, sample queries).

### ADK (Agent Development Kit) Integration

A sample ADK agent is included in `mcp/search_agent/`. It uses `McpToolset` to connect to the MCP server and exposes the search tools to a Gemini model.

#### Quick Start with adk run

```bash
cd vector-search-backend/mcp
uv run --with google-adk --with mcp adk run search_agent
```

This starts an interactive chat — type a query like "find me vintage leather bags" and press Enter.

#### Running with adk web

```bash
cd vector-search-backend/mcp
uv run --with google-adk --with mcp adk web
```

Then open the browser UI and select `search_agent`.

#### Agent Code

See `mcp/search_agent/agent.py`:

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

#### Deployment Note

When deploying ADK agents with MCP tools, the agent and its `McpToolset` must be defined **synchronously** at module level in `agent.py` (not inside an async function). The example above follows this pattern.
