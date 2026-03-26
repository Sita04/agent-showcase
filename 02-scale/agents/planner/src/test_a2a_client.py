import asyncio
import json
import uuid
import httpx

A2A_SERVER_URL = "http://localhost:8080"

async def test_a2a_server():
    print(f"Connecting to A2A Server at {A2A_SERVER_URL}...\n")
    
    prompt = "Inventory Alert: Northeast Region is critically low on 'Rare Japanese Anime Figure'. Please order 2 units ASAP. Max budget $50 per unit."
    
    # Generate a random unique ID for the message as required by the A2A spec
    msg_id = str(uuid.uuid4())
    
    json_rpc_payload = {
        "jsonrpc": "2.0",
        "id": "req-12345",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": msg_id,
                "parts": [{"text": prompt}],
                "role": "user"
            }
        }
    }

    try:
        print("➡️  Sending A2A JSON-RPC 'message/send' request...")
        async with httpx.AsyncClient(timeout=120.0) as client: 
            response = await client.post(
                f"{A2A_SERVER_URL}/",
                json=json_rpc_payload
            )
            
            if response.status_code != 200:
                print(f"❌ Server returned HTTP error: {response.status_code}")
                print(response.text)
                return

            result = response.json()
            
            if "error" in result:
                print("❌ Server returned JSON-RPC error:")
                print(json.dumps(result["error"], indent=2))
                return

            print("✅ Request accepted. Server processing completed...\n")
            print("==================================================")
            print("🎯 A2A SERVER RESPONSE (JSON-RPC)")
            print("==================================================")
            
            task = result.get("result", {})
            
            # The A2A spec uses parts array instead of root
            artifacts = task.get("artifacts", [])
            final_report = "No report returned."
            if artifacts and "parts" in artifacts[-1]:
                parts = artifacts[-1]["parts"]
                if len(parts) > 0 and "text" in parts[0]:
                    final_report = parts[0]["text"]
                
            print(final_report)
            
            print("\n--------------------------------------------------")
            print("Raw JSON Response:")
            print(json.dumps(result, indent=2))
            
    except httpx.ConnectError:
        print(f"❌ Could not connect to {A2A_SERVER_URL}. Is the server running?")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_a2a_server())
