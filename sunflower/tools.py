import asyncio

class ToolRegistry:
    """
    Handles physical environment executions like bash, scripts, and other OS level tasks.
    In the future, this will restrict directories or run via docker-in-docker for sandboxing.
    """
    @staticmethod
    async def execute_bash(command: str) -> str:
        """Executes a bash/shell command asynchronously and returns stdout/stderr"""
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
                
            # Truncating at 3500 chars to avoid hitting Telegram's 4096 character message limit
            final_out = output[:3500]
            if len(output) > 3500:
                final_out += "\n...[Output Truncated]"
                
            return f"```bash\n{final_out}\n```"
        except Exception as e:
            return f"❌ Execution Error: {str(e)}"
