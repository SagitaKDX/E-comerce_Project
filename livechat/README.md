# Live Support Chat System

This is a real-time chat system for customer support integrated with the e-commerce platform. It allows customers to chat with support agents for assistance with their purchases, questions, or issues.

## Features

- Real-time chat using WebSockets (Django Channels)
- CRM agent dashboard to handle customer inquiries
- Support for both authenticated and anonymous users
- Chat session management
- Automatic agent assignment
- Chat history preservation

## Requirements

- Django 5.0+
- Channels 4.0.0
- Daphne 4.0.0
- Channels-Redis 4.1.0
- Redis server (for channel layers)

## Setup

1. Install required packages:
   ```
   pip install channels==4.0.0 daphne==4.0.0 channels-redis==4.1.0 redis==5.2.1
   ```

2. Ensure Redis server is installed and running:
   - For Windows, download from: https://github.com/tporadowski/redis/releases
   - For Linux: `sudo apt install redis-server && sudo systemctl start redis`
   - For Mac: `brew install redis && brew services start redis`
   - Verify Redis is running: `redis-cli ping` (should return "PONG")

3. **IMPORTANT**: Run the Daphne server for WebSockets (in a separate terminal):
   ```
   python run_daphne.py
   ```
   This starts the WebSocket server on port 9000. The chat system will not work without this server running.

4. Run the Django development server (in another terminal):
   ```
   python manage.py runserver
   ```

5. Access the application at:
   - Customer chat: http://localhost:8000/livechat/widget/
   - Agent dashboard: http://localhost:8000/livechat/agent/dashboard/

## Troubleshooting WebSockets

If chat messages aren't appearing or connections fail:

1. Verify both servers are running:
   - Django server (port 8000) - For HTTP requests
   - Daphne server (port 9000) - For WebSocket connections

2. Check WebSocket server status:
   - Visit http://localhost:8000/livechat/websocket-health/
   - Should show "WebSocket server is running correctly"

3. Test WebSocket connection:
   - Visit http://localhost:8000/livechat/websocket-test/
   - The test page should show "WebSocket connection established successfully"

4. Check Redis connectivity:
   ```
   redis-cli ping
   ```
   Should return "PONG"

5. Check browser console for WebSocket errors (usually prefixed with "ws://")

## Usage

### For Customers:
1. Click on the "Live Support" button in the navigation bar or floating button on mobile
2. Fill in the chat form with your query subject
3. Start chatting with a support agent

### For Agents:
1. Login as a CRM user
2. Access the agent dashboard
3. View waiting chats and your active chats
4. Assign chats to yourself to start responding to customers

## Configuration

The chat system uses Django Channels with a Redis backend for WebSocket communication. Configuration is managed in `settings.py`:

```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

You can modify the Redis host and port as needed for your environment. 