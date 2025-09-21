# RentSpot Trading Bot

A WebSocket-based trading bot for monitoring and executing trades on the RentSpot platform with proper rate limiting and connection management.

## Features

- Single WebSocket connection with proper rate limiting
- Automatic reconnection with exponential backoff
- Comprehensive subscription management
- Real-time trade execution
- Detailed logging and statistics
- Connection pooling to prevent blacklisting

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Solana wallet with SOL for trading

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:
```env
WS_URI=wss://pumpportal.fun/api/data
TRADE_URL=https://pumpportal.fun/api/trade-local
PUBLIC_KEY=your_public_key
PRIVATE_KEY=your_private_key
RPC_ENDPOINT=https://api.mainnet-beta.solana.com
```

Replace `your_public_key` and `your_private_key` with your Solana wallet credentials.

## Usage

Start the bot:
```bash
python src/rent_spot_bot.py
```

### Trading Parameters

Default settings:
- Trade amount: 0.0001 SOL
- Priority fee: 0.00001 SOL
- Bribery fee: 0.00001 SOL
- Slippage: 10%
- Minimum balance: 0.01 SOL
- Minimum liquidity: 2.0 SOL
- Maximum price threshold: 0.1 SOL

## WebSocket Client Features

The WebSocket client (`websocket_client.py`) provides:
- Dynamic subscription management
- Connection statistics tracking
- Automatic ping/pong handling
- Graceful error recovery
- Rate limiting to prevent blacklisting

### Subscription Management

```python
from websocket_client import WebSocketClient

client = WebSocketClient()

# Subscribe to new tokens
await client.subscribe_token("token_address")

# Subscribe to account trades
await client.subscribe_account("account_address")

# Unsubscribe when needed
await client.unsubscribe_token("token_address")
await client.unsubscribe_account("account_address")

# Monitor events
await client.start_monitoring()
```

## Important Notes

1. **Single WebSocket Connection**: The bot maintains a single WebSocket connection to prevent blacklisting.
2. **Rate Limiting**: Built-in rate limiting ensures compliance with API restrictions.
3. **Error Handling**: Comprehensive error handling with automatic reconnection.
4. **Logging**: Detailed logging for monitoring bot performance and debugging.

## Troubleshooting

Common issues and solutions:

1. Connection Issues:
   - Verify WebSocket URI is correct
   - Check internet connection
   - Ensure proper rate limiting

2. Trade Execution Errors:
   - Verify wallet has sufficient SOL
   - Check RPC endpoint status
   - Validate trade parameters

3. Subscription Issues:
   - Use single connection for all subscriptions
   - Implement proper unsubscribe when needed
   - Monitor connection statistics

## Statistics and Monitoring

The bot provides detailed statistics:
- Total messages received
- Connection drops
- Ping success rate
- Message processing statistics

Access statistics through the WebSocket client:
```python
client = WebSocketClient()
# After some time running...
print(f"Total Messages: {client.total_messages}")
print(f"Connection Drops: {client.connection_drops}")
print(f"Successful Pings: {client.successful_pings}")
```

## Security

- Never share your private key
- Keep .env file secure
- Regular monitoring of trade activity
- Implement proper error handling
