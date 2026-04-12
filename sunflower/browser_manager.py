import json
import asyncio
from sunflower.config import Config

class BrowserManager:
    # Class-level registry to keep clients alive and prevent session termination
    _active_clients = {} # { user_id: client_instance }

    def __init__(self, config: Config):
        self.config = config

    async def run_web_task(self, task: str, user_id: int, mode: str = "silent"):
        """
        Executes a browser mission. 
        In Cloud Mode, it starts a background pilot to keep the session alive.
        """
        # 1. Budget & Model Guard
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low OpenRouter Balance (${balance}). Please replenish your credits."}

        current_model = self.config.default_model
        rec_model = "anthropic/claude-3.5-sonnet"
        
        # 2. Engine Selection (Cloud vs Local)
        if self.config.browser_api_key:
            return await self._run_cloud_session(task, user_id, rec_model if "claude" in rec_model else current_model)
        else:
            return await self._run_local_session(task, user_id, current_model)

    async def _run_cloud_session(self, task: str, user_id: int, model_id: str):
        from browser_use_sdk.v3 import AsyncBrowserUse
        from sunflower.bot import SunflowerBot
        
        cloud_model = "claude-sonnet-4.6" if "claude" in model_id.lower() else "gpt-4o"
        
        # Instantiate and store client to prevent garbage collection
        client = AsyncBrowserUse(api_key=self.config.browser_api_key)
        self._active_clients[user_id] = client
        
        try:
            # 1. Create session to get the Live Link immediately
            session = await client.sessions.create(task=task, model=cloud_model)
            live_url = session.live_url
            
            # 2. Launch the ACTUAL agent run as a background task
            # We don't 'await' it here so we can return the link to Telegram immediately
            asyncio.create_task(self._background_pilot(client, task, cloud_model, user_id))
            
            return {
                "output": "🚀 *Background Pilot Engaged*\nThe agent is now steering your browser.",
                "live_url": live_url,
                "session_id": session.id
            }
        except Exception as e:
            self._active_clients.pop(user_id, None)
            return {"error": f"Cloud Browser Error: {str(e)}"}

    async def _background_pilot(self, client, task, model, user_id):
        """
        Keeps the session alive and notifies the user upon completion.
        """
        from sunflower.bot import SunflowerBot
        try:
            # This is the call that actually performs the work and keeps session active
            result = await client.run(task, model=model)
            
            # Send notification back to Telegram
            if SunflowerBot.instance:
                bot = SunflowerBot.instance.bot
                final_text = (
                    f"✅ *Browser Mission Complete*\n\n"
                    f"🏁 *Result:* {result.output}\n\n"
                    f"_Session closed safely._"
                )
                await bot.send_message(user_id, final_text, parse_mode="Markdown")
        except Exception as e:
            if SunflowerBot.instance:
                await SunflowerBot.instance.bot.send_message(user_id, f"❌ *Browser Pilot Failed:* {str(e)}")
        finally:
            # Cleanup
            self._active_clients.pop(user_id, None)

    async def _run_local_session(self, task: str, user_id: int, model_id: str):
        # Local sessions are blocking and simpler (for now)
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
