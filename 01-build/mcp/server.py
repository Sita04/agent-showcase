
"""
MCP server for Vector Search 2.0 demo app.

A thin proxy to the Cloud Run REST API that exposes product search
capabilities to MCP clients (Claude Desktop, Cursor, Claude Code, etc.).

Usage:
    uv run server.py              # stdio transport (default)
    mcp dev server.py             # MCP Inspector (browser UI)
"""

import json
import logging
import sys

import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (critical for stdio transport — stdout corrupts JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE = "https://ac-web2-761793285222.us-central1.run.app"

mcp = FastMCP("vector-search-backend")


# ---------------------------------------------------------------------------
# Resource: datasets
# ---------------------------------------------------------------------------


@mcp.resource("vectorsearch://datasets")
async def list_datasets() -> str:
    """List available product search datasets with metadata.

    Returns dataset IDs, names, descriptions, embedding models,
    dimensions, and sample queries for each available dataset.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{API_BASE}/api/datasets")
        resp.raise_for_status()

    datasets = resp.json()
    # Return only the fields useful to an agent
    summary = []
    for ds in datasets:
        summary.append({
            "dataset_id": ds.get("dataset_id"),
            "dataset_name": ds.get("dataset_name"),
            "dataset_desc": ds.get("dataset_desc"),
            "dataset_size": ds.get("dataset_size"),
            "emb_model": ds.get("emb_model"),
            "emb_dims": ds.get("emb_dims"),
            "distance_metric": ds.get("distance_metric"),
            "sample_query": ds.get("sample_query"),
        })
    return json.dumps(summary, indent=2)


# ---------------------------------------------------------------------------
# Tool: search_products
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_products(
    query: str,
    dataset_id: str = "mercari1m_mm2",
    rows: int = 10,
    filter: str = "",
) -> str:
    """Search the Mercari product catalog (2.8M items) using Vector Search 2.0.

    Uses semantic search with reranking for best results.
    Multimodal datasets (e.g. mercari3m_multimodal) support text-to-image search.

    Args:
        query: Search query text (e.g. "men's beach shoes", "vintage camera")
        dataset_id: Dataset to search. Use the datasets resource to see available options.
        rows: Number of results to return (1-100, default 10).
        filter: JSON metadata filter (e.g. '{"price": {"$lt": 50}}').
    """
    # Build REST API payload
    payload: dict = {
        "query": query,
        "dataset_id": dataset_id,
        "rows": min(max(rows, 1), 100),
        "use_semantic_search": True,
        "use_text_search": False,
        "use_rerank": "ranking_api",
    }

    if filter:
        try:
            payload["filter"] = json.loads(filter)
        except json.JSONDecodeError:
            return "Error: `filter` must be a valid JSON string (e.g. '{\"price\": {\"$lt\": 50}}')."

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{API_BASE}/api/query", json=payload)
    except httpx.TimeoutException:
        return "Error: Search request timed out (30s). The backend may be cold-starting — try again in a moment."
    except httpx.RequestError as e:
        return f"Error: Could not connect to search API: {e}"

    if resp.status_code == 400:
        error_data = resp.json()
        details = error_data.get("details", [])
        msgs = [d.get("msg", "") for d in details if d.get("msg")]
        return f"Validation error: {'; '.join(msgs) if msgs else resp.text}"

    if resp.status_code != 200:
        return f"Error: Search API returned status {resp.status_code}"

    data = resp.json()
    items = data.get("items", [])
    latencies = data.get("latencies", {})
    used_knn = data.get("used_knn")

    if not items:
        return "No results found."

    # Format results as readable text for the LLM
    lines = [f"Found {len(items)} results (search: {latencies.get('query', 0):.2f}s, "
             f"index: {'kNN' if used_knn else 'ANN' if used_knn is False else 'N/A'}):\n"]

    for i, item in enumerate(items, 1):
        name = item.get("name", "")
        desc = item.get("description", "")
        img_url = item.get("img_url", "")
        url = item.get("url", "")
        score = item.get("dense_dist") or item.get("sparse_dist") or item.get("rerank_score") or 0

        line = f"{i}. {name}"
        if desc:
            # Truncate long descriptions
            short_desc = desc[:150] + "..." if len(desc) > 150 else desc
            line += f"\n   {short_desc}"
        if url:
            line += f"\n   URL: {url}"
        if img_url:
            line += f"\n   Image: {img_url}"
        line += f"\n   Score: {score:.4f}"
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: generate_sample_query
# ---------------------------------------------------------------------------


@mcp.tool()
async def generate_sample_query(dataset_id: str = "mercari3m_text") -> str:
    """Generate a random sample search query for exploring the product catalog.

    Uses Gemini to create a realistic shopper query. Useful for demos or
    discovering what kinds of products are in the catalog.

    Args:
        dataset_id: Dataset context for query generation.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{API_BASE}/api/generate_query",
                json={"dataset_id": dataset_id},
            )
    except httpx.TimeoutException:
        return "Error: Query generation timed out (15s). Try again."
    except httpx.RequestError as e:
        return f"Error: Could not connect to API: {e}"

    if resp.status_code != 200:
        return f"Error: API returned status {resp.status_code}"

    return resp.text


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
