import asyncio
import os
from sunflower.config import Config

class BrowserManager:
    """
    Sunflower Browser Engine (v10.0) — Sovereign & Secure

    Key principles:
    - Playwright runs inside the bot container (no Browserless sidecar needed).
    - Credentials are NEVER passed to the LLM. They go through browser-use's
      `sensitive_data` dict, which injects them directly into browser DOM
      while the LLM only sees safe placeholder names.
    - Session persistence: after first login, cookies are saved to a per-user
      vault file. Subsequent runs load the session and skip the login entirely.
    """

    def __init__(self, config: Config):
        self.config = config
        self.vault = os.path.join(os.getcwd(), "sunflower", "vault", "browser")
        os.makedirs(self.vault, exist_ok=True)

    def _session_path(self, user_id: int, platform: str) -> str:
        """Per-user, per-platform session file path."""
        user_vault = os.path.join(self.vault, str(user_id))
        os.makedirs(user_vault, exist_ok=True)
        return os.path.join(user_vault, f"{platform}_session.json")

    def _resolve_platform(self, task: str) -> tuple[str | None, dict]:
        """
        Detect which platform the task references and return its stored creds.
        Returns (platform_name, creds_dict). creds_dict is empty if no match.
        """
        accounts = self.config.get_path("browser.accounts", {})
        for platform, creds in accounts.items():
            if platform.lower() in task.lower():
                return platform, creds
        return None, {}

    async def run_web_task(self, task: str, user_id: int) -> dict:
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low Fuel: OpenRouter balance is ${balance}. Top up at openrouter.ai."}
        return await self._run_session(task, user_id)

    async def _run_session(self, task: str, user_id: int) -> dict:
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_openai import ChatOpenAI

        platform, creds = self._resolve_platform(task)
        session_path = self._session_path(user_id, platform or "default")

        # --- Browser: local Playwright Chromium, no remote sidecar ---
        browser_config = BrowserConfig(
            headless=True,
            # Load persisted session if it exists (skips login on repeat runs)
            storage_state=session_path if os.path.exists(session_path) else None,
        )
        browser = Browser(config=browser_config)

        # --- LLM: our standard OpenRouter connection ---
        llm = ChatOpenAI(
            model=self.config.default_model,
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
        )

        # --- Credentials: passed as sensitive_data, NEVER in the prompt ---
        # The LLM only sees placeholder names (e.g., "sf_user", "sf_pass").
        # browser-use injects the real values directly into the DOM.
        sensitive_data = {}
        augmented_task = task

        if platform and creds:
            u, p = creds.get("user"), creds.get("pass")
            if u:
                sensitive_data["sf_user"] = u
                augmented_task += f" Use sf_user as the username/email."
            if p:
                sensitive_data["sf_pass"] = p
                augmented_task += f" Use sf_pass as the password."
            totp_secret = creds.get("totp")
            if totp_secret:
                import pyotp
                try:
                    sensitive_data["sf_totp"] = pyotp.TOTP(totp_secret).now()
                    augmented_task += " Use sf_totp as the 2FA code."
                except Exception:
                    pass  # TOTP failure is non-fatal; agent will handle 2FA prompt

        agent = Agent(
            task=augmented_task,
            llm=llm,
            browser=browser,
            sensitive_data=sensitive_data if sensitive_data else None,
        )

        # Fire the mission in the background and report back when done
        asyncio.create_task(
            self._run_and_report(agent, browser, user_id, platform, session_path)
        )

        return {
            "output": (
                f"🚀 *Browser Mission Engaged*\n"
                f"Goal: {task}\n"
                f"Platform: {platform.upper() if platform else 'Web'}\n\n"
                f"Running in the background. I'll message you when it's done."
            )
        }

    async def _run_and_report(self, agent, browser, user_id: int, platform: str | None, session_path: str):
        """Run the agent, persist the session on success, report back to the user."""
        from sunflower.bot import SunflowerBot
        if not SunflowerBot.instance:
            return
        bot = SunflowerBot.instance.bot

        try:
            history = await agent.run()
            result = history.final_result()

            # Persist session so next run skips login entirely
            try:
                await browser.export_storage_state(session_path)
                session_note = f"\n_Session saved — {platform or 'web'} login will be automatic next time._"
            except Exception:
                session_note = ""

            await bot.send_message(
                user_id,
                f"✅ *Mission Complete*\n\n{result}{session_note}",
                parse_mode="Markdown"
            )
        except Exception as e:
            await bot.send_message(user_id, f"❌ *Browser Mission Failed:* {str(e)}")
        finally:
            await browser.close()

    async def clear_session(self, user_id: int, platform: str) -> bool:
        """Delete a saved session so the agent logs in fresh next time."""
        path = self._session_path(user_id, platform)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
