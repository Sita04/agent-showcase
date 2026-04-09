import json

def render_search_ui(categories: list, persona: str = None) -> dict:
    """
    Renders A2UI JSON for product search results, grouped by category.
    """
    cards = []
    for group in categories:
        category_name = group.get("category", "Unknown Category")
        products = group.get("options", [])
        
        # Add a category header card (no image, no button)
        cards.append({
            "Card": {
                "children": [
                    {
                        "Text": {
                            "text": category_name,
                            "style": "title"
                        }
                    }
                ]
            }
        })
        
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
                                "text": f"${price}",
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

    # Add a follow-up menu card at the end
    follow_up_children = [
        {
            "Text": {
                "text": "What would you like to do next?",
                "style": "title"
            }
        }
    ]
    
    scenarios = []
    if persona == "adam":
        scenarios = [
            ("Solo Yosemite Trip ($600)", "Solo backpacking trip to Yosemite. Budget: $600"),
            ("Daily Bicycle Commute ($300)", "Upgrade daily bicycle commute gear. Budget: $300"),
            ("Expedition Prep ($1200)", "Durable gear for a hiking expedition. Budget: $1200")
        ]
    elif persona == "lucy":
        scenarios = [
            ("Music Festival Tech ($250)", "Aesthetic tech for a music festival. Budget: $250"),
            ("Art Studio Supplies ($150)", "Supplies for my art studio. Budget: $150"),
            ("Aesthetic Tech ($200)", "Desk accessories and tech. Budget: $200")
        ]
    elif persona == "elena":
        scenarios = [
            ("Business Casual Wardrobe ($800)", "Business casual capsule wardrobe. Budget: $800"),
            ("Corporate Gala ($300)", "Elegant dress for a corporate gala. Budget: $300"),
            ("Weekend Getaway ($400)", "Casual chic outfits for a weekend getaway. Budget: $400")
        ]
        
    for text, message in scenarios:
        follow_up_children.append({
            "Button": {
                "child": { "Text": { "text": text } },
                "action": { "command": "send_message", "params": { "message": message } }
            }
        })
        
    cards.append({
        "Card": {
            "children": follow_up_children
        }
    })

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
