# Vector Search Backend API Specification

**Base URL**: [`https://ac-web2-761793285222.us-central1.run.app`](https://ac-web2-761793285222.us-central1.run.app)

A Flask-based search backend powered by Google Cloud Vertex AI Vector Search 2.0. Provides semantic, text, and hybrid search over product datasets (~2.8M Mercari items). CORS is enabled for all origins.

---

## Endpoints

### 1. `POST /api/query` — Search Products

The main search endpoint. Supports semantic search (dense vector embeddings), text search (keyword matching), and hybrid search (both combined with Reciprocal Rank Fusion).

Also supports `GET` with query parameters.

#### Request Body (JSON)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
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
|---|---|---|
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

#### Example GET Request

```
GET /api/query?query=vintage+leather+jacket&rows=20&use_semantic_search=true&use_text_search=true&rrf_alpha=0.6
```

#### Response (200 OK)

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
|-------|------|-------------|
| `items` | array | List of search result items |
| `items[].id` | string | Item ID (extracted from data object resource name) |
| `items[].name` | string | Product name |
| `items[].description` | string | Product description |
| `items[].img_url` | string | Product image URL |
| `items[].url` | string | Product listing URL |
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

#### Response (200 OK)

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
|-------|------|-------------|
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

#### Request Body (JSON)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dataset_id` | string | No | `"mercari3m_text_128"` | Dataset ID to generate a query for |

#### Example GET Request

```
GET /api/generate_query?dataset_id=mercari3m_text_128
```

#### Response (200 OK)

Returns a plain text string (not JSON) with the generated query.

```
vintage ceramic coffee mugs
```

---

## Datasets

Each dataset is indexed with a specific embedding task type, which determines the default query task type used at search time:

- **`RETRIEVAL_DOCUMENT`** datasets: queries default to `RETRIEVAL_QUERY` (asymmetric query-document matching)
- **`SEMANTIC_SIMILARITY`** datasets: queries default to `SEMANTIC_SIMILARITY` (symmetric similarity matching)
- **BYOE** datasets: task type is not applicable — embeddings are generated by external models (Word2Vec, multimodal-embedding-001)

| Dataset ID | Embedding Model | Dims | Distance Metric | BYOE | Index Task Type | Query Task Type | Description |
|------------|----------------|------|-----------------|------|-----------------|-----------------|-------------|
| `mercari3m_text_128` | gemini-embedding-001 | 128 | DOT_PRODUCT | No | RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | Default. Reduced-dimension Gemini embeddings |
| `mercari3m_text` | gemini-embedding-001 | 768 | DOT_PRODUCT | No | RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | Full-dimension Gemini embeddings |
| `mercari3m_text_similarity` | gemini-embedding-001 | 768 | DOT_PRODUCT | No | SEMANTIC_SIMILARITY | SEMANTIC_SIMILARITY | Symmetric matching for "find similar items" use cases |
| `mercari3m_word2vec` | Gensim Word2Vec | 100 | COSINE | Yes | N/A | N/A | Word2Vec BYOE — fastest inference, word-level semantics |
| `mercari3m_multimodal` | multimodal-embedding-001 | 1408 | DOT_PRODUCT | Yes | N/A | N/A | Multimodal embeddings encoding item images |

All datasets contain ~2,874,425 Mercari product listings with fields: `name`, `description`, `img_url`, `url`.

---

## Notes

- **CORS**: All origins are allowed.
- **BYOE datasets** (`mercari3m_word2vec`, `mercari3m_multimodal`): Semantic search generates query embeddings at search time (Word2Vec or multimodal-embedding-001). The `latencies.gen_query_emb` field reflects this cost. Text search works the same as auto-embedding datasets.
- **Reranking**: When `use_rerank=ranking_api` is set, results are reranked using the Discovery Engine Ranking API (`semantic-ranker-512@latest`). The `rerank_score` field is populated and item order reflects the reranked order.
- **Session**: The service assigns a session ID via cookies. The `/api/generate_query` endpoint uses this to avoid repeating previously generated queries.
