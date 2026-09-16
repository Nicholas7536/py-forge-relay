# Game Server Infrastructure & Discord Integration

Asynchronous bi-directional chat relay and event pipeline between Minecraft and Discord using Python asyncio, WebSockets, and thread-isolated RCON.

## Project Context

This project was originally developed and operated on a headless Linux (Ubuntu) server. This repository contains the modular, reconstructed Python skeleton of the core relay pipeline.

It assumes you already have a Minecraft-to-Python connection in place—specifically, the original deployment used a custom Minecraft Forge mod to push in-game events over WebSockets. If you are integrating this with a different server or mod loader (e.g. Paper, Fabric), you only need to match the simple WebSocket packet format defined in this document.

## Overview

- **Minecraft to Discord**: The Minecraft server (Forge mod) opens a local WebSocket connection to Python and streams JSON event packets (`chat`, `join`, `leave`, `death`). Python relays them to the configured Discord channel.
- **Discord to Minecraft**: Python listens for messages in the Discord relay channel and broadcasts them to Minecraft chat via `/tellraw` commands using RCON.

## Technical Rationale: Thread-Isolated RCON

Minecraft RCON is a synchronous, blocking TCP protocol. Under server tick drops, garbage collection pauses, or network latency spikes, socket reads can hang for multiple seconds.

In standard single-threaded Python asyncio:
- Executing synchronous socket calls directly on the event loop blocks the entire process thread.
- During this block, `discord.py` cannot send timely Gateway heartbeat pings (`Opcode 1`).
- The Discord Gateway assumes the client timed out and closes the connection (`Error 1006 / 4000`), triggering connection drops and reconnect loops.

To solve this, `rcon_client.py` uses `asyncio.to_thread` to execute all blocking socket I/O inside Python's worker thread pool. The main asyncio event loop remains unblocked, keeping Discord Gateway heartbeats stable.

Run the verification benchmark to observe the difference:
```bash
python test_rcon_isolation.py
```

## Setup & Configuration

### 1. Prerequisites
- Python 3.10+
- Minecraft server with RCON enabled in `server.properties`:
  ```properties
  enable-rcon=true
  rcon.port=25575
  rcon.password=your_rcon_password_here
  ```
- Discord bot with **Message Content Intent** enabled.

### 2. Installation
```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=123456789012345678

RCON_HOST=127.0.0.1
RCON_PORT=25575
RCON_PASSWORD=your_rcon_password_here
RCON_TIMEOUT_SECONDS=3.0

WS_HOST=127.0.0.1
WS_PORT=8765
```

### 4. Running the Service
```bash
python main.py
```

## WebSocket Packet Specification

The Python relay listens on `ws://WS_HOST:WS_PORT`. The Forge mod sends standard JSON payloads:

### In-Game Chat
```json
{
  "event": "chat",
  "player": "Steve",
  "message": "Hello from Minecraft"
}
```

### Player Join / Leave
```json
{
  "event": "join",
  "player": "Steve"
}
```
```json
{
  "event": "leave",
  "player": "Steve"
}
```

### Player Death
```json
{
  "event": "death",
  "player": "Steve",
  "message": "Steve fell from a high place"
}
```

## Project Structure

```
py/
├── .env.example            # Environment variable template
├── .gitignore              # Git ignore rules
├── requirements.txt        # Dependencies (discord.py, websockets, python-dotenv, mcrcon)
├── config.py               # Configuration loader and validator
├── rcon_client.py          # Thread-isolated RCON client (asyncio.to_thread)
├── ws_server.py            # WebSocket event receiver for Forge mod
├── discord_bot.py          # Discord client and message handling
├── main.py                 # Application entrypoint and lifecycle coordinator
├── test_rcon_isolation.py  # Benchmark demonstrating thread isolation vs heartbeat jitter
└── README.md               # Documentation
```
