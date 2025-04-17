# -*- coding: utf-8 -*-
import asyncio
from dotenv import load_dotenv
import os
from typing import Any
import httpx
import json
import logging

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

# 環境変数とロギングの設定
load_dotenv()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

server = Server("discord-service")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        # チャンネル管理
        types.Tool(
            name="get-channel",
            description="Get channel information",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to get information about"
                    }
                },
                "required": ["channel_id"]
            }
        ),
        # サーバー管理
        types.Tool(
            name="get-guild",
            description="Get guild (server) information",
            inputSchema={
                "type": "object",
                "properties": {
                    "guild_id": {
                        "type": "string",
                        "description": "Guild ID to get information about"
                    }
                },
                "required": ["guild_id"]
            }
        ),
        # メッセージ管理
        types.Tool(
            name="send-message",
            description="Send a message to a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to send message to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Message content to send"
                    }
                },
                "required": ["channel_id", "content"]
            }
        ),
        types.Tool(
            name="get-messages",
            description="Get recent messages from a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to get messages from"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages to retrieve (default: 50, max: 100)"
                    }
                },
                "required": ["channel_id"]
            }
        )
    ]

async def make_discord_request(
    client: httpx.AsyncClient, 
    method: str,
    endpoint: str,
    token: str,
    json_data: dict | None = None
) -> dict[str, Any] | None:
    """Make a request to Discord API"""
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    try:
        url = f"https://discord.com/api/v10{endpoint}"
        logger.debug(f"Making request: {method} {url}")
        
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            timeout=30.0
        )
        
        logger.debug(f"Response status: {response.status_code}")
        
        if response.status_code == 204:
            return {"success": True}
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        logger.error(f"Discord API error: {str(e)}")
        return {"error": str(e)}

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> list[types.TextContent]:
    """Handle tool execution"""
    if not arguments:
        return [types.TextContent(type="text", text="No arguments provided")]

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        return [types.TextContent(type="text", text="DISCORD_BOT_TOKEN is not set")]

    async with httpx.AsyncClient() as client:
        try:
            result = None
            
            if name == "get-channel":
                channel_id = arguments["channel_id"]
                result = await make_discord_request(
                    client, "GET", f"/channels/{channel_id}", token
                )
                
            elif name == "get-guild":
                guild_id = arguments["guild_id"]
                result = await make_discord_request(
                    client, "GET", f"/guilds/{guild_id}", token
                )
                
            elif name == "send-message":
                channel_id = arguments["channel_id"]
                content = arguments["content"]
                
                result = await make_discord_request(
                    client, "POST", f"/channels/{channel_id}/messages",
                    token, json_data={"content": content}
                )
                
            elif name == "get-messages":
                channel_id = arguments["channel_id"]
                limit = min(int(arguments.get("limit", 50)), 100)
                result = await make_discord_request(
                    client, "GET", f"/channels/{channel_id}/messages?limit={limit}",
                    token
                )
                
            else:
                return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

            if result is None:
                return [types.TextContent(type="text", text="Operation completed")]
            elif "error" in result:
                return [types.TextContent(type="text", text=f"Error: {result['error']}")]
            else:
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            logger.error(f"Tool execution error: {str(e)}")
            return [types.TextContent(type="text", text=f"Error occurred: {str(e)}")]

async def main():
    """Main function to run the server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="discord-service",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def run_server():
    """Entry point for the server"""
    asyncio.run(main())

if __name__ == "__main__":
    run_server()