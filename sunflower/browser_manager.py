import json
import asyncio
from sunflower.config import Config

class BrowserManager:
    def __init__(self, config: Config):
        self.config = config
        self._active_sessions = {}

    async def run_web_task(self, task: str, user_id: int, mode: str = "silent"):
        """
        Executes a browser mission. 
        Returns a dictionary with 'output', 'live_url', and 'screenshots'.
        """
        # 1. Budget & Model Guard
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low OpenRouter Balance (${balance}). Please replenish your credits."}

        current_model = self.config.default_model
        rec_model = "anthropic/claude-3.5-sonnet" # Optimal for browser tasks
        
        # 2. Engine Selection (Cloud vs Local)
        if self.config.browser_api_key:
            return await self._run_cloud_session(task, user_id, rec_model if "claude" in rec_model else current_model)
        else:
            return await self._run_local_session(task, user_id, current_model)

    async def _run_cloud_session(self, task: str, user_id: int, model_id: str):
        from browser_use_sdk.v3 import AsyncBrowserUse
        
        # Cloud SDK uses short names for models it optimizes
        cloud_model = "claude-sonnet-4.6" if "claude" in model_id.lower() else "gpt-4o"
        
        client = AsyncBrowserUse(api_key=self.config.browser_api_key)
        
        try:
            # Create a session to get the live_url immediately
            session = await client.sessions.create(
                task=task,
                model=cloud_model
            )
            
            self._active_sessions[user_id] = session.id
            live_url = session.live_url
            
            # Start running and monitor (we could stream here, but for now we poll/await)
            # In a real bot, we'd start a background task to notify the user of progress
            result = await client.sessions.get(session.id)
            
            # Since result.run() is simpler for one-offs, let's use the polling loop or similar
            # For the first version, we'll wait for completion but return the live_url early if requested
            # result = await client.run(task, model=cloud_model)
            
            return {
                "output": "Mission Started. Use the Live Link to monitor.",
                "live_url": live_url,
                "session_id": session.id
            }
        except Exception as e:
            return {"error": f"Cloud Browser Error: {str(e)}"}

    async def _run_local_session(self, task: str, user_id: int, model_id: str):
        try:
            from browser_use import Agent
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(
                model=model_id,
                base_url="https://openrouter.ai/api/v1",
                api_key=self.config.api_key
            )
            
            agent = Agent(task=task, llm=llm)
            result = await agent.run()
            
            return {
                "output": result.final_result(),
                "live_url": None,
                "status": "completed"
            }
        except Exception as e:
            return {"error": f"Local Browser Error: {str(e)}"}
