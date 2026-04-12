import json
import asyncio
import os
from sunflower.config import Config

class BrowserManager:
    # Class-level registry to keep clients alive
    _active_clients = {} 

    def __init__(self, config: Config):
        self.config = config

    async def run_web_task(self, task: str, user_id: int):
        """
        Executes a browser mission. 
        Implements a 'Streaming Reporter' that sends checkpoints & screenshots to Telegram.
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
            # 1. Start session
            session = await client.sessions.create(task=task, model=cloud_model)
            live_url = session.live_url
            
            # 2. Engage Background Pilot with Streaming
            asyncio.create_task(self._streaming_report_pilot(client, task, cloud_model, user_id, session.id))
            
            return {
                "output": f"🎬 *Mission Storyboard Engaged*\nUsing model: `{cloud_model}`\n\nI will send progress snapshots directly to this chat.",
                "live_url": live_url,
                "session_id": session.id
            }
        except Exception as e:
            self._active_clients.pop(user_id, None)
            return {"error": f"Cloud Browser Error: {str(e)}"}

    async def _streaming_report_pilot(self, client, task, model, user_id, session_id):
        """
        The Storyboard Pilot:
        - Iterates over steps in real-time.
        - Sends text checkpoints to Telegram.
        - Sends periodic screenshots as photos.
        """
        from sunflower.bot import SunflowerBot
        import pyotp
        
        if not SunflowerBot.instance:
            return

        bot = SunflowerBot.instance.bot
        
        # Instructions for Autonomous Auth
        system_extension = (
            "If you encounter a 2FA / TOTP screen and have a 'totp_secret', use the 'pyotp' library "
            "to generate a 6-digit code. Always describe your visual state clearly for the user."
        )

        try:
            # Engage the Streaming Runner
            run = client.run(task, model=model, session_id=session_id, system_prompt_extension=system_extension)
            
            last_screenshot_at = 0
            async for step in run:
                # 1. Send Text Progress
                msg = f"📍 *Step {step.number}*: {step.next_goal}\n🌐 *URL*: {step.url}"
                await bot.send_message(user_id, msg, parse_mode="Markdown")
                
                # 2. Visual Storyboard (Take a screenshot if 15s+ passed since last one)
                current_time = asyncio.get_event_loop().time()
                if current_time - last_screenshot_at > 15:
                    try:
                        # Use the result-provided screenshots or a CDP snap
                        # For now, we take a direct CDP snapshot for recency
                        screenshot_resp = await client.sessions.get(session_id)
                        if getattr(screenshot_resp, 'screenshot_url', None):
                            await bot.send_photo(user_id, screenshot_resp.screenshot_url, caption=f"📸 Progress View (Step {step.number})")
                            last_screenshot_at = current_time
                    except:
                        pass # Silently skip if screenshot fails
            
            # 3. Final Report
            final_report = (
                f"✅ *Mission Complete*\n\n"
                f"🏁 *Result:* {run.result.output}\n\n"
                f"_Session closed safely._"
            )
            await bot.send_message(user_id, final_report, parse_mode="Markdown")
            
        except Exception as e:
            await bot.send_message(user_id, f"❌ *Pilot Intercepted Error:* {str(e)}")
        finally:
            self._active_clients.pop(user_id, None)

    async def _run_local_session(self, task: str, user_id: int, model_id: str):
        try:
            from browser_use import Agent
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(model=model_id, base_url="https://openrouter.ai/api/v1", api_key=self.config.api_key)
            agent = Agent(task=task, llm=llm)
            result = await agent.run()
            return {"output": result.final_result(), "status": "completed"}
        except Exception as e:
            return {"error": f"Local Browser Error: {str(e)}"}
