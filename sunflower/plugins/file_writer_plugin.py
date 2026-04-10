import os
from sunflower.tools import BasePlugin

class FileWriterPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "write_to_file",
                "description": "Creates or overwrites a file. ALWAYS use this instead of trying to write files using bash 'echo', because bash cannot handle complex string escaping.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The file path to save the content to (e.g., sunflower/plugins/weather_plugin.py)"
                        },
                        "content": {
                            "type": "string",
                            "description": "The raw string content or code to write inside the file."
                        }
                    },
                    "required": ["path", "content"]
                }
            }
        }
        
    @classmethod
    async def execute(cls, path: str, content: str, **kwargs) -> str:
        try:
            # Create subdirectories if they don't exist
            dir_name = os.path.dirname(os.path.abspath(path))
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
                
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"✅ Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            return f"❌ IOError: Failed to write to {path}: {str(e)}"
