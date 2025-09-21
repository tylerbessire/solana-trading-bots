import asyncio
import websockets
import json

async def subscribe():
uri = "wss://pumpportal.fun/api/data"
async with websockets.connect(uri) as websocket:
    
    # Subscribing to token creation events
    payload = {
        "method": "subscribeNewToken",
    }
    await websocket.send(json.dumps(payload))

    # Subscribing to trades made by accounts
    payload = {
        "method": "subscribeAccountTrade",
        "keys": ["AArPXm8JatJiuyEffuC1un2Sc835SULa4uQqDcaGpAjV"]  # array of accounts to watch
    }
    await websocket.send(json.dumps(payload))

    # Subscribing to trades on tokens
    payload = {
        "method": "subscribeTokenTrade",
        "keys": ["91WNez8D22NwBssQbkzjy4s2ipFrzpmn5hfvWVe2aY5p"]  # array of token CAs to watch
    }
    await websocket.send(json.dumps(payload))
    
    async for message in websocket:
        print(json.loads(message))

# Run the subscribe function
asyncio.get_event_loop().run_until_complete(subscribe())
