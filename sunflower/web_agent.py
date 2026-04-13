import asyncio
import base64
import json
import os
from tempfile import NamedTemporaryFile
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from sunflower.config import Config
from openai import AsyncOpenAI

class WebAgent:
    """
    Raw Playwright Web Agent — Vision-based loop
    """
    def __init__(self, config: Config):
        self.config = config
        self.vault = os.path.join(os.getcwd(), "sunflower", "vault", "browser")
        os.makedirs(self.vault, exist_ok=True)
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
        )

    def _session_path(self, profile: str, platform: str) -> str:
        path_dir = os.path.join(self.vault, profile)
        os.makedirs(path_dir, exist_ok=True)
        return os.path.join(path_dir, f"{platform}_session.json")

    async def run(self, task: str, profile: str = "agent", platform: str = "default") -> dict:
        session_path = self._session_path(profile, platform)
        
        storage_state = None
        if os.path.exists(session_path):
            storage_state = session_path

        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir="", # An empty string or temp dir is needed if we don't persist globally
                    storage_state=storage_state,
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                
                page = await context.new_page()
                await stealth_async(page)
                
                # Try setting standard viewport
                await page.set_viewport_size({"width": 1280, "height": 800})
                
                result = await self._vision_loop(page, task)
                
                # Save session 
                await context.storage_state(path=session_path)
                await context.close()
                return {"output": result}
                
        except Exception as e:
            return {"error": f"Browser Error: {str(e)}"}

    async def _vision_loop(self, page, task: str) -> str:
        max_steps = 15
        
        system_prompt = (
            "You are an autonomous web browser agent. "
            "You are given a task and a screenshot of the current page. "
            "You must return ONLY a JSON object to decide the next action.\n\n"
            "Action schema:\n"
            '{"type": "navigate", "url": "https://..."}\n'
            '{"type": "click", "selector": "CSS selector to click"}\n'
            '{"type": "type", "selector": "CSS selector", "text": "text to type"}\n'
            '{"type": "scroll", "direction": "down|up"}\n'
            '{"type": "done", "result": "The final outcome to report to the user"}\n\n'
            "Return valid JSON and nothing else."
        )

        history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Your task: {task}"}
        ]

        for step in range(max_steps):
            await asyncio.sleep(2) # Stabilize DOM
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
            b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            # Create vision message
            vision_msg = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Step {step+1}. What is on screen? What should I do next? Respond in strict JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }
            
            # Send to LLM
            response = await self.client.chat.completions.create(
                model=self.config.default_model,
                messages=history + [vision_msg],
                temperature=0.0
            )
            
            # Clean JSON response
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"): content = content[7:].rstrip("`").strip()
            elif content.startswith("```"): content = content[3:].rstrip("`").strip()
            
            try:
                action = json.loads(content)
                history.append({"role": "assistant", "content": content})
                
                a_type = action.get("type")
                if a_type == "navigate":
                    await page.goto(action.get("url"))
                elif a_type == "click":
                    await page.click(action.get("selector"))
                elif a_type == "type":
                    await page.fill(action.get("selector"), action.get("text"))
                elif a_type == "scroll":
                    direction = action.get("direction", "down")
                    if direction == "down":
                        await page.evaluate("window.scrollBy(0, 800)")
                    else:
                        await page.evaluate("window.scrollBy(0, -800)")
                elif a_type == "done":
                    return action.get("result", "Task completed.")
                else:
                    return f"Error: Agent returned invalid action type: {a_type}"
                    
            except json.JSONDecodeError:
                return f"Error: Agent failed to return valid JSON. Response was: {content}"
            except Exception as e:
                # If an action fails (e.g. timeout on click), we just report it and stop.
                # A more robust loop would pass the error back as a user message and let it recover.
                return f"Execution Error on step {step+1}: {str(e)}"

        return "Task failed: Max steps reached."
