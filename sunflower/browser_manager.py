import json
import asyncio
import os
from sunflower.config import Config

class BrowserManager:
    """
    Sunflower Sovereign Engine (v8.0)
    Optimized for Frictionless UX: Sign-in and Forget.
    Uses Local Browserless sidecar with Per-User Persistent Vaults.
    """
    def __init__(self, config: Config):
        self.config = config
        self.base_vault = os.path.join(os.getcwd(), "sunflower", "vault", "browser")
        os.makedirs(self.base_vault, exist_ok=True)

    async def run_web_task(self, task: str, user_id: int):
        """
        Launches a sovereign browser mission with automatic credential bridge.
        """
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low Fuel: OpenRouter Balance is ${balance}."}

        return await self._run_sovereign_session(task, user_id)

    async def _run_sovereign_session(self, task: str, user_id: int):
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_openai import ChatOpenAI
        import pyotp
        
        # 1. Hardware Initialization
        user_vault = os.path.join(self.base_vault, str(user_id))
        os.makedirs(user_vault, exist_ok=True)
        
        browser_config = BrowserConfig(
            headless=True,
            wss_url="ws://browser:3000", 
            persistent_context_dir=user_vault 
        )
        browser = Browser(config=browser_config)
        
        # 2. Intelligence Selection
        llm = ChatOpenAI(
            model=self.config.default_model, 
            base_url="https://openrouter.ai/api/v1", 
            api_key=self.config.api_key
        )
        
        # 3. Universal Keyring Detection
        system_extension = (
            "SAFETY RULE: If you see a CAPTCHA or a 'Login' button that won't go away, "
            "immediately STOP and inform the user to use the Visual Rescue Link."
        )
        
        accounts = self.config.get_path("browser.accounts", {})
        target_platform = None
        for platform in accounts.keys():
            if platform.lower() in task.lower():
                target_platform = platform
                break
        
        if target_platform:
            creds = accounts[target_platform]
            u, p = creds.get("user"), creds.get("pass")
            if u and p:
                auth_instr = f" Use these {target_platform} credentials if prompted: User: {u} / Pass: {p}."
                
                # Check for TOTP/2FA Secret
                totp_secret = creds.get("totp")
                if totp_secret:
                    try:
                        totp_code = pyotp.TOTP(totp_secret).now()
                        auth_instr += f" If a 2FA/TOTP code is required, use this code: {totp_code}."
                    except:
                        pass
                system_extension += auth_instr

        # 4. Ignition
        agent = Agent(task=task, llm=llm, browser=browser, system_prompt_extension=system_extension)
        
        # 6. Mission Control: Background the pilot
        asyncio.create_task(self._sovereign_report_pilot(agent, task, user_id, browser))
        
        return {
            "output": "🚀 *Sovereign Engine Engaged*\nYour private profile vault is active. Sequoia has been handed the credentials.",
            "live_url": f"http://{os.getenv('VPS_IP', 'localhost')}:3000"
        }

    async def _sovereign_report_pilot(self, agent, task, user_id, browser):
        from sunflower.bot import SunflowerBot
        if not SunflowerBot.instance:
            return
        bot = SunflowerBot.instance.bot
        
        try:
            # Execute the mission
            history = await agent.run()
            
            # Final Report
            final_report = f"✅ *Mission Complete*\n\n🏁 *Result:* {history.final_result()}"
            await bot.send_message(user_id, final_report, parse_mode="Markdown")
            
        except Exception as e:
            err_msg = str(e).lower()
            await bot.send_message(user_id, f"❌ *Pilot Intercepted Error:* {str(e)}")
            
            # Rescue Signaling
            if any(x in err_msg for x in ["captcha", "timeout", "element not found"]):
                await bot.send_message(user_id, "💡 *Rescue Tip*: I might be stuck at a security puzzle. Use the Visual Rescue link above to help me through!", parse_mode="Markdown")
        finally:
            await browser.close()
