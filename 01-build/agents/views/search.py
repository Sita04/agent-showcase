import json

def render_search_ui(products: list) -> dict:
    """
    Renders A2UI JSON for product search results.
    Follows the inferred schema from documentation snippets.
    """
    cards = []
    for item in products:
        sku = item.get("id", "N/A")
        name = item.get("name", "Unknown Product")
        price = item.get("price", 0.0)
        img_url = item.get("img_url", "https://via.placeholder.com/300x200?text=No+Image")
        similarity = item.get("similarity", 0.0)

        card = {
            "Card": {
                "children": [
                    {
                        "Image": {
                            "src": img_url,
                            "alt": name
                        }
                    },
                    {
                        "Text": {
                            "text": name,
                            "style": "title"
                        }
                    },
                    {
                        "Text": {
                            "text": f"${price} ({round(similarity * 100)}% Match)" if isinstance(similarity, float) else f"${price}",
                            "style": "subtitle"
                        }
                    },
                    {
                        "Button": {
                            "child": {
                                "Text": {
                                    "text": "Add to Cart"
                                }
                            },
                            "action": {
                                "name": "add_to_cart_click",
                                "context": [
                                    { "key": "sku", "value": { "literalString": sku } }
                                ]
                            }
                        }
                    }
                ]
            }
        }
        cards.append(card)

    envelope = {
        "beginRendering": {
            "surfaceId": "search-results",
            "content": {
                "Column": {
                    "children": cards
                }
            }
        }
    }
    return envelope
