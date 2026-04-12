import json
import asyncio
import os
from sunflower.config import Config

class BrowserManager:
    """
    Lean & Mean Browser Mission Controller (v6.0)
    Optimized for transparency, security, and zero-bloat.
    """
    _active_clients = {} 
    _paused_sessions = {}

    def __init__(self, config: Config):
        self.config = config

    async def run_web_task(self, task: str, user_id: int):
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low Fuel: OpenRouter Balance is ${balance}."}

        if self.config.browser_api_key:
            return await self._run_cloud_session(task, user_id)
        else:
            return await self._run_local_session(task, user_id)

    async def _run_cloud_session(self, task: str, user_id: int):
        from browser_use_sdk.v3 import AsyncBrowserUse
        
        # Clean model mapping
        model_id = self.config.default_model
        cloud_model = "claude-sonnet-4.6" if "claude" in model_id.lower() else "gpt-4o"
        
        client = AsyncBrowserUse(api_key=self.config.browser_api_key)
        self._active_clients[user_id] = client
        
        try:
            # Ignition: Create idle session with persistence
            session = await client.sessions.create(model=cloud_model, keep_alive=True)
            
            # Mission Control: Background the pilot
            asyncio.create_task(self._streaming_report_pilot(client, task, cloud_model, user_id, session.id))
            
            return {
                "output": "🚀 *Mission Engine Online*\nSequoia is taking control. Watch for progress checkpoints below.",
                "live_url": session.live_url
            }
        except Exception as e:
            self._active_clients.pop(user_id, None)
            return {"error": f"Ignition Failed: {str(e)}"}

    async def _streaming_report_pilot(self, client, task, model, user_id, session_id):
        from sunflower.bot import SunflowerBot
        import pyotp
        
        if not SunflowerBot.instance:
            return
        bot = SunflowerBot.instance.bot
        
        system_instructions = (
            "Safety Priority: Never attempt a CAPTCHA more than twice. "
            "If stuck, describe the view and wait. Use pyotp for 2FA."
        )

        strikes = 0
        try:
            # Stream the task
            run = client.run(task, model=model, session_id=session_id, system_prompt_extension=system_instructions)
            
            step_count = 0
            async for update in run:
                step_count += 1
                # Resilient attribute extraction (Wozniak Standard)
                goal = getattr(update, 'next_goal', getattr(update, 'text', 'Navigating...'))
                url = getattr(update, 'url', 'Browser State')
                
                # 1. Report Progress
                checkpoint = f"📍 *Step {step_count}*: {goal}\n🌐 *State*: `{url}`"
                await bot.send_message(user_id, checkpoint, parse_mode="Markdown")
                
                # 2. Safety Check
                if any(x in str(goal).lower() for x in ["captcha", "verify", "robot", "human"]):
                    strikes += 1
                    if strikes >= 2:
                        await bot.send_message(user_id, "🚨 *Security Halt*: Repeated challenges detected. Handing over to prevent lockout.")
                        session_info = await client.sessions.get(session_id)
                        await bot.send_message(user_id, f"🔒 *Manual Rescue Required*\nOpen in Desktop Incognito: [Mission Control]({session_info.live_url})\n\nSolve the puzzle, then type `Resume`.")
                        self._paused_sessions[user_id] = session_id
                        await client.sessions.stop(session_id, strategy="task")
                        return

            # 3. Success Report
            final_report = f"✅ *Mission Finished*\n\n🏁 *Outcome:* {run.result.output}"
            await bot.send_message(user_id, final_report, parse_mode="Markdown")
            
        except Exception as e:
            await bot.send_message(user_id, f"❌ *Pilot Report Exception:* {str(e)}")
        finally:
            if user_id not in self._paused_sessions:
                self._active_clients.pop(user_id, None)

    async def resume_session(self, user_id: int):
        if user_id not in self._paused_sessions:
            return {"error": "No paused mission found."}
            
        session_id = self._paused_sessions.pop(user_id)
        client = self._active_clients.get(user_id)
        
        asyncio.create_task(self._streaming_report_pilot(client, "Continue the original task.", "claude-sonnet-4.6", user_id, session_id))
        return {"output": "🔄 *Resume Signal Received*: Continuing mission..."}

    async def _run_local_session(self, task, user_id, model_id):
        # ... (Legacy local support as fallback)
        return {"error": "Local mode disabled for secure Wozniak missions."}
