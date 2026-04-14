from sunflower.tools import BasePlugin
from sunflower.config import Config
import praw

class RedditPlugin(BasePlugin):
    """
    Direct API access to Reddit via PRAW.
    Extremely reliable, zero browser needed.
    """

    @classmethod
    def get_tool_schema(cls) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "reddit_post",
                    "description": "Submit a new text or link post to a subreddit.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subreddit": {"type": "string", "description": "Name of subreddit (no r/)"},
                            "title": {"type": "string"},
                            "body": {"type": "string", "description": "Text body (or link URL)"},
                            "is_link": {"type": "boolean"},
                            "profile": {"type": "string", "description": "Which stored profile/account to use"}
                        },
                        "required": ["subreddit", "title", "body", "profile"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reddit_search",
                    "description": "Search Reddit natively without auth.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "subreddit": {"type": "string", "description": "Optional: Restrict to subreddit"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    @classmethod
    def _get_reddit(cls, config: Config, profile: str) -> praw.Reddit | None:
        raw_tokens = config.get_path(f"profiles.{profile}.accounts.reddit", {})
        client_id = raw_tokens.get("client_id")
        client_secret = raw_tokens.get("client_secret")
        username = raw_tokens.get("username")
        password = raw_tokens.get("password")
        
        if not all([client_id, client_secret, username, password]):
            return None
            
        return praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=f"sunflower:{client_id}:v1.0 (by u/{username})"
        )

    @classmethod
    async def execute(cls, user_id: int = 0, **kwargs) -> str:
        # PRAW is technically synchronous, so we run it in a thread or just execute directly (mostly IO bound)
        import asyncio
        return await asyncio.to_thread(cls._sync_execute, **kwargs)
        
    @classmethod
    def _sync_execute(cls, **kwargs) -> str:
        # This acts as a router since this plugin handles multiple tools
        # We need the task name to route, but the LLM executor only passes args right now.
        # Wait, the LLM executor calls it, but doesn't pass the tool name!
        # Actually in tools.py, execute_tool just calls plugin.execute.
        # I'll just check kwargs to see which one it is.
        
        config = Config()
        
        if "query" in kwargs:
            return cls._reddit_search(kwargs)
            
        if "title" in kwargs:
            return cls._reddit_post(kwargs, config)
            
        return "❌ Sub-command not recognized."

    @classmethod
    def _reddit_search(cls, args):
        reddit = praw.Reddit(client_id="dummy", client_secret="dummy", user_agent="sunflower:search:v1.0")
        try:
            sub_name = args.get("subreddit", "all")
            query = args.get("query")
            sub = reddit.subreddit(sub_name)
            results = []
            for submission in sub.search(query, limit=5):
                results.append(f"Title: {submission.title}\nURL: https://reddit.com{submission.permalink}\nScore: {submission.score}\n")
            return "\n".join(results) if results else "No results found."
        except Exception as e:
            return f"❌ Reddit Search error: {str(e)}"

    @classmethod
    def _reddit_post(cls, args, config):
        profile = args.get("profile")
        reddit = cls._get_reddit(config, profile)
        if not reddit:
            return f"❌ No valid Reddit API tokens found for profile '{profile}'. Set up via /connect."
            
        try:
            sub = reddit.subreddit(args["subreddit"])
            title = args.get("title")
            body = args.get("body")
            is_link = args.get("is_link", False)
            
            if is_link:
                submission = sub.submit(title=title, url=body)
            else:
                submission = sub.submit(title=title, selftext=body)
                
            return f"✅ Posted to r/{args['subreddit']}: https://reddit.com{submission.permalink}"
        except Exception as e:
            return f"❌ Reddit Post error: {str(e)}"
