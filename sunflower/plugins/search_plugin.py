import asyncio
from sunflower.tools import BasePlugin


class SearchPlugin(BasePlugin):
    """
    Web search tool. Zero-config by default (DuckDuckGo).
    Automatically upgrades to Exa.ai if `exa_api_key` is set in config.

    This should always be tried BEFORE launching a browser for research tasks.
    It is faster, cheaper, and more reliable for information retrieval.
    """

    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the web for current information, news, facts, or research. "
                    "Always use this FIRST for any research task — it is far faster than "
                    "launching a browser. Returns titles, URLs, and content snippets. "
                    "After receiving results, synthesize and return a summary to the user. "
                    "Do NOT call web_agent for tasks that are pure information lookup."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query."
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return. Default 5, max 10."
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    @classmethod
    async def execute(cls, query: str = "", num_results: int = 5, **kwargs) -> str:
        if not query:
            return "❌ No query provided."

        num_results = min(max(1, int(num_results)), 10)

        from sunflower.config import Config
        config = Config()
        exa_key = config.get_path("exa_api_key")

        if exa_key:
            result = await cls._search_exa(query, num_results, exa_key)
            if result:
                return result
            # Fall through to DuckDuckGo on Exa failure

        return await cls._search_ddg(query, num_results)

    @classmethod
    async def _search_exa(cls, query: str, num_results: int, api_key: str) -> str | None:
        """Exa.ai — semantic search built for AI agents. Activated by exa_api_key in config."""
        try:
            from exa_py import Exa
            loop = asyncio.get_event_loop()
            exa = Exa(api_key)
            results = await loop.run_in_executor(
                None,
                lambda: exa.search_and_contents(
                    query,
                    num_results=num_results,
                    use_autoprompt=True,
                    text={"max_characters": 400}
                )
            )
            if not results.results:
                return None

            lines = [f"🔍 *Search Results* (Exa) — `{query}`\n"]
            for i, r in enumerate(results.results, 1):
                lines.append(f"**{i}. {r.title}**")
                lines.append(f"🔗 {r.url}")
                if r.text:
                    lines.append(f"{r.text.strip()[:400]}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            print(f"[SearchPlugin] Exa error: {e} — falling back to DuckDuckGo")
            return None

    @classmethod
    async def _search_ddg(cls, query: str, num_results: int) -> str:
        """DuckDuckGo — zero-config fallback. Works with no API key."""
        try:
            from duckduckgo_search import DDGS
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: list(DDGS().text(query, max_results=num_results))
            )
            if not results:
                return f"No search results found for: `{query}`"

            lines = [f"🔍 *Search Results* — `{query}`\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"**{i}. {r.get('title', 'No title')}**")
                lines.append(f"🔗 {r.get('href', '')}")
                body = r.get('body', '').strip()
                if body:
                    lines.append(body[:400])
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Search failed: {str(e)}"
