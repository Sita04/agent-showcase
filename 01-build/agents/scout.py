# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

def render_search_ui(categories: list, persona: str = None) -> dict:
    """
    Renders A2UI JSON for product search results, grouped by category.
    """
    cards = []
    for group in categories:
        category_name = group.get("category", "Unknown Category")
        products = group.get("options", [])
        
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
                                        "text": "Select"
                                    }
                                },
                                "action": {
                                    "name": "select_item_click",
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
