import httpx
from sunflower.tools import BasePlugin
from sunflower.config import Config

class DelegationPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "paperclip__delegate_task",
                "description": "Delegates a large or asynchronous task to the Paperclip orchestration backend by creating an Issue ticket. Do not use this for quick synchronous tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "A short descriptive title for the task (limit 100 characters)"},
                        "description": {"type": "string", "description": "The detailed instructions and context for the sub-agent."},
                    },
                    "required": ["title", "description"]
                }
            }
        }
        
    @classmethod
    async def execute(cls, title: str, description: str, **kwargs) -> str:
        config = Config()
        pc_conf = config.get_paperclip_config()
        url = pc_conf.get("url", "http://localhost:3100")
        api_key = pc_conf.get("api_key")
        company_id = pc_conf.get("company_id")
        
        if not api_key or not company_id:
            return "❌ Paperclip configuration missing! Tell the user to use `/paperclip set_key` and `/paperclip set_company` to link the Telegram Bot up to Paperclip."
            
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        endpoint = f"{url}/api/companies/{company_id}/issues"
        
        payload = {
            "title": title,
            "description": description,
            "priority": "medium",
            "status": "todo"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(endpoint, json=payload, headers=headers, timeout=10.0)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    issue_id = data.get("identifier") or data.get("id", "Unknown ID")
                    return f"✅ Ticket created successfully. Issue ID: {issue_id}. The Paperclip backend has taken over this task."
                else:
                    return f"❌ Failed to create issue. HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"❌ HTTP Request failed: {str(e)}"
