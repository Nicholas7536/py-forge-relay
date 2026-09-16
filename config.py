"""
Configuration loader and validator for the Minecraft-Discord relay service.
Loads variables from environment or a local .env file.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

# Automatically look for .env in project root
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


@dataclass(frozen=True)
class Config:
    # Discord Settings
    discord_bot_token: str
    discord_channel_id: int

    # Minecraft RCON Settings
    rcon_host: str
    rcon_port: int
    rcon_password: str
    rcon_timeout: float

    # Inbound WebSocket Bridge Settings
    ws_host: str
    ws_port: int

    @classmethod
    def load(cls) -> "Config":
        """Loads and validates configuration from environment variables."""
        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        channel_id_raw = os.getenv("DISCORD_CHANNEL_ID", "").strip()

        errors = []
        if not token or token == "your_discord_bot_token_here":
            errors.append("DISCORD_BOT_TOKEN is missing or set to placeholder.")

        if not channel_id_raw or not channel_id_raw.isdigit():
            errors.append("DISCORD_CHANNEL_ID must be a valid numeric Discord channel ID.")

        if errors:
            raise ValueError(
                "Configuration Error:\n  - " + "\n  - ".join(errors) +
                "\nPlease copy .env.example to .env and configure your values."
            )

        return cls(
            discord_bot_token=token,
            discord_channel_id=int(channel_id_raw),
            rcon_host=os.getenv("RCON_HOST", "127.0.0.1").strip(),
            rcon_port=int(os.getenv("RCON_PORT", "25575")),
            rcon_password=os.getenv("RCON_PASSWORD", "").strip(),
            rcon_timeout=float(os.getenv("RCON_TIMEOUT_SECONDS", "3.0")),
            ws_host=os.getenv("WS_HOST", "127.0.0.1").strip(),
            ws_port=int(os.getenv("WS_PORT", "8765")),
        )
