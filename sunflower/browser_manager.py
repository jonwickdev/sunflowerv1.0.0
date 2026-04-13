import asyncio
import os
from sunflower.config import Config


class BrowserManager:
    """
    Sunflower Browser Engine (v11.0) — Profile-Aware & Secure

    Profile system:
    - "agent"    → Sunflower's own accounts (default for general tasks)
    - "personal" → User's personal accounts
    - Any other named profile → User-defined (e.g., "work", "client_acme")

    Session persistence:
    - Sessions are stored at vault/{profile}/{platform}_session.json per user
    - After first login, cookies are reused automatically — no repeat credential entry

    Credentials are NEVER passed as text to the LLM. They go through
    browser-use's `sensitive_data` dict which injects values directly into
    the browser DOM, keeping them invisible to the AI.
    """

    def __init__(self, config: Config):
        self.config = config
        self.vault = os.path.join(os.getcwd(), "sunflower", "vault", "browser")
        os.makedirs(self.vault, exist_ok=True)

    def _session_path(self, user_id: int, profile: str, platform: str) -> str:
        """Sessions are namespaced by user AND profile to prevent cross-contamination."""
        path_dir = os.path.join(self.vault, str(user_id), profile)
        os.makedirs(path_dir, exist_ok=True)
        return os.path.join(path_dir, f"{platform}_session.json")

    def _resolve_creds(self, task: str, profile_name: str) -> tuple[str | None, dict]:
        """
        Detect which platform the task targets and return creds from the named profile.
        If the named profile has no account for that platform, falls back to checking
        other profiles automatically (agent → personal → others).

        Returns (platform_name, creds_dict).
        """
        profiles = self.config.list_profiles()

        def find_platform_in_profile(prof_data: dict) -> tuple[str | None, dict]:
            accounts = prof_data.get("accounts", {})
            for p, creds in accounts.items():
                if p.lower() in task.lower():
                    return p, creds
            return None, {}

        # Try the requested profile first
        target_profile = profiles.get(profile_name, {})
        platform, creds = find_platform_in_profile(target_profile)
        if platform:
            return platform, creds

        # Fallback: check other profiles in priority order (agent → personal → rest)
        fallback_order = ["agent", "personal"] + [k for k in profiles if k not in ("agent", "personal", profile_name)]
        for p_name in fallback_order:
            if p_name == profile_name:
                continue
            platform, creds = find_platform_in_profile(profiles.get(p_name, {}))
            if platform:
                return platform, creds

        return None, {}

    async def run_web_task(self, task: str, user_id: int, profile: str = "agent") -> dict:
        balance = await self.config.get_balance()
        if balance < 0.10:
            return {"error": f"⚠️ Low Fuel: OpenRouter balance is ${balance}. Top up at openrouter.ai."}
        return await self._run_session(task, user_id, profile)

    async def _run_session(self, task: str, user_id: int, profile: str) -> dict:
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_openai import ChatOpenAI

        platform, creds = self._resolve_creds(task, profile)
        session_path = self._session_path(user_id, profile, platform or "default")

        # --- Browser: local Playwright Chromium. No remote sidecar needed. ---
        browser_config = BrowserConfig(
            headless=True,
            # Load persisted session if it exists — skips login on repeat runs
            storage_state=session_path if os.path.exists(session_path) else None,
        )
        browser = Browser(config=browser_config)

        # --- LLM: our standard OpenRouter connection ---
        llm = ChatOpenAI(
            model=self.config.default_model,
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
        )

        # --- Credentials: go through sensitive_data, NEVER into the prompt ---
        # The LLM only sees placeholder names. Real values are injected to the DOM.
        sensitive_data = {}
        augmented_task = task

        if platform and creds:
            u, p = creds.get("user"), creds.get("pass")
            if u:
                sensitive_data["sf_user"] = u
                augmented_task += " Use sf_user as the username/email."
            if p:
                sensitive_data["sf_pass"] = p
                augmented_task += " Use sf_pass as the password."
            totp_secret = creds.get("totp")
            if totp_secret:
                import pyotp
                try:
                    sensitive_data["sf_totp"] = pyotp.TOTP(totp_secret).now()
                    augmented_task += " Use sf_totp as the 2FA/TOTP code."
                except Exception:
                    pass  # Non-fatal — agent will handle 2FA prompt if it appears

        profile_label = self.config.get_path(f"profiles.{profile}.display_name", profile)

        agent = Agent(
            task=augmented_task,
            llm=llm,
            browser=browser,
            sensitive_data=sensitive_data if sensitive_data else None,
        )

        asyncio.create_task(
            self._run_and_report(agent, browser, user_id, profile, platform, session_path)
        )

        return {
            "output": (
                f"🚀 *Browser Mission Engaged*\n"
                f"Profile: {profile_label}\n"
                f"Platform: {platform.upper() if platform else 'Web'}\n\n"
                f"Running in the background. You'll get a message when it's done."
            )
        }

    async def _run_and_report(
        self, agent, browser, user_id: int,
        profile: str, platform: str | None, session_path: str
    ):
        """Run the agent, persist session on success, report back to user."""
        from sunflower.bot import SunflowerBot
        if not SunflowerBot.instance:
            return
        bot = SunflowerBot.instance.bot

        try:
            history = await agent.run()
            result = history.final_result()

            # Persist session so next run skips login entirely
            session_note = ""
            try:
                await browser.export_storage_state(session_path)
                session_note = f"\n_Session saved — login will be automatic next time._"
            except Exception:
                pass

            await bot.send_message(
                user_id,
                f"✅ *Mission Complete*\n\n{result}{session_note}",
                parse_mode="Markdown"
            )
        except Exception as e:
            await bot.send_message(user_id, f"❌ *Browser Mission Failed:* {str(e)}")
        finally:
            await browser.close()

    async def clear_session(self, user_id: int, platform: str, profile: str = "personal") -> bool:
        """Delete a saved session so the agent logs in fresh next time."""
        path = self._session_path(user_id, profile, platform)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
