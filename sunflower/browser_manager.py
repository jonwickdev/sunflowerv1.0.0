import json
import asyncio
import os
from sunflower.config import Config

class BrowserManager:
    # Class-level registry to keep clients and sessions alive
    _active_clients = {} 
    _paused_sessions = {} # { user_id: session_id }

    def __init__(self, config: Config):
        self.config = config

    async def run_web_task(self, task: str, user_id: int):
        """
        Executes a browser mission. 
        Implements a 'Streaming Reporter' with Safety Strikes for account protection.
        """
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low OpenRouter Balance (${balance}). Please replenish your credits."}

        current_model = self.config.default_model
        
        # Cloud Mode is required for stealth/auth missions
        if self.config.browser_api_key:
            return await self._run_cloud_session(task, user_id, current_model)
        else:
            return await self._run_local_session(task, user_id, current_model)

    async def _run_cloud_session(self, task: str, user_id: int, model_id: str):
        from browser_use_sdk.v3 import AsyncBrowserUse
        
        # Map model to SDK optimized strings
        cloud_model = "claude-sonnet-4.6" if "claude" in model_id.lower() else "gpt-4o"
        
        client = AsyncBrowserUse(api_key=self.config.browser_api_key)
        self._active_clients[user_id] = client
        
        try:
            # 1. Start session idle (no task yet) to allow streaming pilot to take control
            session = await client.sessions.create(model=cloud_model, keep_alive=True)
            live_url = session.live_url
            
            # 2. Engage Background Pilot with Streaming
            asyncio.create_task(self._streaming_report_pilot(client, task, cloud_model, user_id, session.id))
            
            return {
                "output": f"🎬 *Mission Storyboard Engaged*\nUsing model: `{cloud_model}`\n\nI will send progress checkpoints to this chat.",
                "live_url": live_url,
                "session_id": session.id
            }
        except Exception as e:
            self._active_clients.pop(user_id, None)
            return {"error": f"Cloud Browser Error: {str(e)}"}

    async def _streaming_report_pilot(self, client, task, model, user_id, session_id):
        """
        The Storyboard Pilot with Safety Strikes.
        """
        from sunflower.bot import SunflowerBot
        import pyotp
        
        if not SunflowerBot.instance:
            return

        bot = SunflowerBot.instance.bot
        
        system_extension = (
            "If you encounter a 2FA/CAPTCHA screen, attempt to solve it ONLY once. "
            "If you fail or are unsure, describe the challenge clearly and wait for user instructions. "
            "Use pyotp if a totp_secret is available."
        )

        strikes = 0
        try:
            run = client.run(task, model=model, session_id=session_id, system_prompt_extension=system_extension)
            
            last_screenshot_at = 0
            async for step in run:
                # 1. Send Text Progress
                msg = f"📍 *Step {step.number}*: {step.next_goal}\n🌐 *URL*: {step.url}"
                await bot.send_message(user_id, msg, parse_mode="Markdown")
                
                # 2. Safety Strike Detection
                check_text = (step.next_goal or "").lower()
                if any(x in check_text for x in ["captcha", "robot", "verification", "verify your account"]):
                    strikes += 1
                
                if strikes >= 2:
                    # SAFETY HALT: Pause the agent but keep session alive
                    await bot.send_message(user_id, "🚨 *Safety Ceiling Hit*\nI've encountered repeated security challenges. To protect your brand account from a lockout, I have **PAUSED** the mission.")
                    
                    # Provide Takeover Instructions
                    session_resp = await client.sessions.get(session_id)
                    takeover_url = session_resp.live_url
                    
                    takeover_msg = (
                        f"🔒 *MANUAL TAKEOVER REQUIRED*\n\n"
                        f"1. Open this link on your **Laptop/Desktop**: [Mission Control]({takeover_url})\n"
                        f"2. *Pro Tip:* Use Chrome Incognito to bypass CSP issues.\n"
                        f"3. Solve the CAPTCHA manually.\n"
                        f"4. Once done, type `Resume` here to give me back the controls."
                    )
                    await bot.send_message(user_id, takeover_msg, parse_mode="Markdown")
                    
                    self._paused_sessions[user_id] = session_id
                    # We stop the current 'run' but the session stays 'idle' because of keep_alive: true
                    await client.sessions.stop(session_id, strategy="task")
                    return

                # 3. Optional Visual Storyboard
                if self.config.get_path("browser.snapshots", False):
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_screenshot_at > 20:
                        try:
                            screenshot_resp = await client.sessions.get(session_id)
                            if getattr(screenshot_resp, 'screenshot_url', None):
                                await bot.send_photo(user_id, screenshot_resp.screenshot_url, caption=f"📸 Progress Snapshot (Step {step.number})")
                                last_screenshot_at = current_time
                        except:
                            pass 
            
            # 4. Final Report
            final_report = (
                f"✅ *Mission Complete*\n\n"
                f"🏁 *Result:* {run.result.output}\n\n"
                f"_Session closed safely._"
            )
            await bot.send_message(user_id, final_report, parse_mode="Markdown")
            
        except Exception as e:
            await bot.send_message(user_id, f"❌ *Pilot Intercepted Error:* {str(e)}")
        finally:
            if user_id not in self._paused_sessions:
                self._active_clients.pop(user_id, None)

    async def resume_session(self, user_id: int, task: str = "Continue the original mission."):
        """
        Wakes up a paused browser session.
        """
        if user_id not in self._paused_sessions:
            return {"error": "No paused mission found for your ID."}
            
        session_id = self._paused_sessions.pop(user_id)
        client = self._active_clients.get(user_id)
        
        if not client:
            return {"error": "Browser connection lost. Please restart the mission."}
            
        # Re-engage the pilot
        asyncio.create_task(self._streaming_report_pilot(client, task, "claude-sonnet-4.6", user_id, session_id))
        return {"output": "🔄 *Pilot Re-Engaged*\nContinuing the mission from the current state..."}
