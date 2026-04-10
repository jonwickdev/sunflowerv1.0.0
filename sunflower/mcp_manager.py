import asyncio
import contextlib
from copy import deepcopy
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class McpManager:
    """Manages MCP Subprocesses and connections."""
    _stack = None
    _sessions = {} # { "server_name": ClientSession }

    @classmethod
    async def start_all(cls, config):
        cls._sessions.clear()
        if cls._stack:
            await cls._stack.aclose()
        cls._stack = contextlib.AsyncExitStack()
        
        servers = config.get_mcp_config()
        for name, spec in servers.items():
            cmd = spec.get("command")
            args = spec.get("args", [])
            env = spec.get("env", None)
            if not cmd:
                continue
                
            try:
                server_params = StdioServerParameters(command=cmd, args=args, env=env)
                
                read, write = await cls._stack.enter_async_context(stdio_client(server_params))
                session = await cls._stack.enter_async_context(ClientSession(read, write))
                
                await session.initialize()
                cls._sessions[name] = session
                print(f"[MCP] Initialized server: {name}")
            except Exception as e:
                print(f"[MCP Error] Failed to initialize server '{name}': {e}")
                
    @classmethod
    async def close(cls):
        if cls._stack:
            await cls._stack.aclose()
            cls._stack = None
        cls._sessions.clear()

    @classmethod
    async def get_all_tools(cls) -> list:
        tools_list = []
        for server_name, session in cls._sessions.items():
            try:
                tools_response = await session.list_tools()
                for tool in tools_response.tools:
                    mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                    
                    schema = {
                        "type": "function",
                        "function": {
                            "name": mcp_tool_name,
                            "description": tool.description or f"Tool {tool.name} from {server_name}",
                            "parameters": tool.inputSchema
                        }
                    }
                    tools_list.append(schema)
            except Exception as e:
                print(f"[MCP Tool Fetch Error] {server_name}: {e}")
                
        return tools_list

    @classmethod
    async def execute_tool(cls, mcp_tool_name: str, args: dict) -> str:
        parts = mcp_tool_name.split("__", 2)
        if len(parts) != 3:
            return f"Invalid MCP tool name: {mcp_tool_name}"
            
        _, server_name, actual_tool_name = parts
        
        if server_name not in cls._sessions:
            return f"MCP server '{server_name}' is not connected."
            
        session = cls._sessions[server_name]
        try:
            result = await session.call_tool(actual_tool_name, arguments=args)
            if result.isError:
                return f"MCP Error: {result.content}"
            texts = [c.text for c in result.content if getattr(c, 'type', '') == 'text']
            return "\n".join(texts) if texts else str(result.content)
        except Exception as e:
            return f"Error executing MCP tool {actual_tool_name} on {server_name}: {str(e)}"
