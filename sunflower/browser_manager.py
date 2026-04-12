import json
import asyncio
import os
from sunflower.config import Config

class BrowserManager:
    """
    Sunflower Sovereign Engine (v9.0)
    Lethal Cleanup Edition: Zero-Bloat, High-Stability.
    """
    def __init__(self, config: Config):
        self.config = config
        self.base_vault = os.path.join(os.getcwd(), "sunflower", "vault", "browser")
        os.makedirs(self.base_vault, exist_ok=True)

    async def run_web_task(self, task: str, user_id: int):
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low Fuel: OpenRouter Balance is ${balance}."}

        return await self._run_sovereign_session(task, user_id)

    async def _run_sovereign_session(self, task: str, user_id: int):
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_openai import ChatOpenAI
        import pyotp
        
        # 1. User Isolation
        user_vault = os.path.join(self.base_vault, str(user_id))
        os.makedirs(user_vault, exist_ok=True)
        
        # 2. Browser Connect (Local Sidecar)
        browser_config = BrowserConfig(
            headless=True,
            wss_url="ws://browser:3000", 
            persistent_context_dir=user_vault 
        )
        browser = Browser(config=browser_config)
        
        # 3. Intelligence Selection
        llm = ChatOpenAI(
            model=self.config.default_model, 
            base_url="https://openrouter.ai/api/v1", 
            api_key=self.config.api_key
        )
        
        # 4. Credential Injection
        system_extension = (
            "SAFETY: If you see a CAPTCHA or a 'Login' button after typing, "
            "STOP and ask the user to use the Visual Rescue Link."
        )
        
        accounts = self.config.get_path("browser.accounts", {})
        target = next((p for p in accounts if p.lower() in task.lower()), None)
        
        if target:
            creds = accounts[target]
            u, p = creds.get("user"), creds.get("pass")
            if u and p:
                auth_instr = f" Use these {target} credentials: User: {u} / Pass: {p}."
                totp_secret = creds.get("totp")
                if totp_secret:
                    try:
                        totp_code = pyotp.TOTP(totp_secret).now()
                        auth_instr += f" 2FA Code: {totp_code}."
                    except: pass
                system_extension += auth_instr

        # 5. Mission Start
        agent = Agent(task=task, llm=llm, browser=browser, system_prompt_extension=system_extension)
        asyncio.create_task(self._sovereign_report_pilot(agent, user_id, browser))
        
        return {
            "output": "🚀 *Sovereign Engine Engaged*\nUsing local metal. Watch for status updates.",
            "live_url": f"http://{os.getenv('VPS_IP', 'localhost')}:3000"
        }

    async def _sovereign_report_pilot(self, agent, user_id, browser):
        from sunflower.bot import SunflowerBot
        if not SunflowerBot.instance: return
        bot = SunflowerBot.instance.bot
        
        try:
            history = await agent.run()
            final_report = f"✅ *Mission Complete*\n\n🏁 *Result:* {history.final_result()}"
            await bot.send_message(user_id, final_report, parse_mode="Markdown")
        except Exception as e:
            await bot.send_message(user_id, f"❌ *Pilot Error:* {str(e)}")
        finally:
            await browser.close()
