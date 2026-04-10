import asyncio
from sunflower.tools import BasePlugin

class BashPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "execute_bash",
                "description": "Executes a shell command in the local environment to read files, run scripts, modify code, or generate assets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The explicit internal bash command to execute"
                        }
                    },
                    "required": ["command"]
                }
            }
        }
        
    @classmethod
    async def execute(cls, command: str, **kwargs) -> str:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            output = ""
            if stdout:
                output += f"STDOUT:\n{stdout.decode()}\n"
            if stderr:
                output += f"STDERR:\n{stderr.decode()}\n"
                
            if not output:
                output = "Command executed successfully. (No output)"
                
            final_out = output[:3500]
            if len(output) > 3500:
                final_out += "\n...[Output Truncated]"
                
            return f"```bash\n{final_out}\n```"
        except Exception as e:
            return f"❌ Execution Error: {str(e)}"
