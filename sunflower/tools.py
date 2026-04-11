import os
import sys
import importlib
import inspect

class BasePlugin:
    """Base class for all Sunflower Plugins."""
    @classmethod
    def get_tool_schema(cls) -> dict:
        """Returns the JSON schema expected by OpenRouter."""
        return {}
        
    @classmethod
    async def execute(cls, user_id: int = 0, **kwargs) -> str:
        """Executes the plugin logic."""
        return ""

class PluginManager:
    """Dynamically loads and manages all external plugins."""
    _plugins = {}
    
    @classmethod
    def load_plugins(cls):
        """Scans the plugins directory and loads all valid plugins."""
        plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
        if not os.path.exists(plugins_dir):
            return
            
        cls._plugins.clear()
        
        # Add to path so importlib can find it
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)
            
        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                try:
                    # Hot reload if already imported
                    if module_name in sys.modules:
                        module = importlib.reload(sys.modules[module_name])
                    else:
                        module = importlib.import_module(module_name)
                        
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BasePlugin) and obj != BasePlugin:
                            schema = obj.get_tool_schema()
                            if "function" in schema and "name" in schema["function"]:
                                cls._plugins[schema["function"]["name"]] = obj
                except Exception as e:
                    print(f"Failed to load plugin {filename}: {e}")

    @classmethod
    async def get_all_schemas(cls) -> list:
        schemas = [plugin.get_tool_schema() for plugin in cls._plugins.values() if plugin.get_tool_schema()]
        try:
            from sunflower.mcp_manager import McpManager
            mcp_schemas = await McpManager.get_all_tools()
            schemas.extend(mcp_schemas)
        except Exception as e:
            print(f"[PluginManager] Error fetching MCP tools: {e}")
        return schemas
        
    @classmethod
    async def execute_tool(cls, name: str, kwargs: dict, user_id: int = 0) -> str:
        if name.startswith("mcp__"):
            from sunflower.mcp_manager import McpManager
            return await McpManager.execute_tool(name, kwargs)

        # Re-scan for newly added plugins if necessary
        if not cls._plugins:
            cls.load_plugins()

        if name in cls._plugins:
            try:
                plugin = cls._plugins[name]
                return await plugin.execute(user_id=user_id, **kwargs)
            except Exception as e:
                return f"Error executing plugin {name}: {str(e)}"
        return f"Plugin {name} not found."
