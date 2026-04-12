import json
import asyncio
import os
from sunflower.config import Config

class BrowserManager:
    """
    Sunflower Sovereign Engine (v7.1)
    Professional-grade Local Browser Management via Browserless.
    Optimized for Persistence, Stealth, and Zero-Bloat.
    """
    _active_contexts = {} 

    def __init__(self, config: Config):
        self.config = config
        self.vault_dir = os.path.join(os.getcwd(), "sunflower", "vault", "browser")
        os.makedirs(self.vault_dir, exist_ok=True)

    async def run_web_task(self, task: str, user_id: int):
        """
        Launches a sovereign browser mission using the local sidecar.
        """
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low Fuel: OpenRouter Balance is ${balance}."}

        return await self._run_sovereign_session(task, user_id)

    async def _run_sovereign_session(self, task: str, user_id: int):
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_openai import ChatOpenAI
        
        # 1. Hardware Initialization (Connected to local Browserless)
        browser_config = BrowserConfig(
            headless=True,
            wss_url="ws://browser:3000", # Connect to the sidecar
            persistent_context_dir=self.vault_dir # THE VAULT: Sessions stay logged in
        )
        
        browser = Browser(config=browser_config)
        
        # 2. Intelligence Selection
        model_id = self.config.default_model
        llm = ChatOpenAI(
            model=model_id, 
            base_url="https://openrouter.ai/api/v1", 
            api_key=self.config.api_key
        )
        
        # 3. Ignition
        agent = Agent(task=task, llm=llm, browser=browser)
        
        # 4. Mission Control: Background the pilot
        asyncio.create_task(self._sovereign_report_pilot(agent, task, user_id, browser))
        
        return {
            "output": "🚀 *Sovereign Engine Engaged*\nConnected to local VPS metal. Persistent session active.",
            "live_url": f"http://{os.getenv('VPS_IP', 'localhost')}:3000" # Link to the Visual Debugger
        }

    async def _sovereign_report_pilot(self, agent, task, user_id, browser):
        from sunflower.bot import SunflowerBot
        if not SunflowerBot.instance:
            return
        bot = SunflowerBot.instance.bot
        
        try:
            # Execute the mission
            # The local Agent.run() provides internal logging
            history = await agent.run()
            
            # Final Report
            final_report = f"✅ *Mission Complete*\n\n🏁 *Result:* {history.final_result()}"
            await bot.send_message(user_id, final_report, parse_mode="Markdown")
            
        except Exception as e:
            await bot.send_message(user_id, f"❌ *Sovereign Pilot Error:* {str(e)}")
        finally:
            await browser.close()
