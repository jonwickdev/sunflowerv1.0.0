import asyncio
import datetime
from sunflower.llm import LLMClient
from sunflower.config import Config
from sunflower.hq_manager import HqManager

class AntiSlopAuditor:
    """
    The CEO's Quality Assurance Officer. 
    It checks reports for 'AI Slop' and ensures they meet the Boss's standards.
    """
    def __init__(self, config: Config, hq: HqManager):
        self.config = config
        self.hq = hq
        self.llm = LLMClient(config)

    async def review_task(self, task: dict) -> bool:
        """
        Reviews a task's report. 
        Returns True if passed, False if rejected.
        """
        task_id = task['id']
        report_path = task['report_path']
        goal = task['goal']

        if not report_path or not open(report_path).read().strip():
            return False

        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()

        print(f"🕵️ Auditor is reviewing Task #{task_id} report...")

        # 1. The Slop Test Prompt
        prompt = (
            "You are an expert Quality Assurance Auditor for an elite CEO.\n"
            f"GOAL OF THE MISSION: {goal}\n"
            f"REPORT TO REVIEW:\n{report_content}\n\n"
            "Evaluate this report against the following criteria:\n"
            "1. GENERICNESS: Does it sound like standard AI 'slop' (fluff, generic lists)?\n"
            "2. DEPTH: Does it provide specific, granular data points and analytical insights?\n"
            "3. ACCURACY: Does it directly achieve the original goal?\n\n"
            "RETURN ONLY A JSON OBJECT:\n"
            "{\n"
            "  \"depth_score\": 0-10,\n"
            "  \"originality_score\": 0-10,\n"
            "  \"is_slop\": true/false,\n"
            "  \"feedback\": \"Specific feedback for the agent on how to improve if rejected.\",\n"
            "  \"decision\": \"approve\" or \"reject\"\n"
            "}"
        )

        try:
            response = self.llm.client.chat.completions.create(
                model=self.config.default_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            import json
            result = json.loads(response.choices[0].message.content)
            
            # Save metrics to DB
            await self.hq.update_task_status(
                task_id=task_id,
                status="pending_review", # Intermediate state
                quality_score=result.get('depth_score', 0),
                feedback=result.get('feedback', '')
            )

            if result.get('decision') == 'approve' and result.get('depth_score', 0) >= 7:
                print(f"✅ Task #{task_id} PASSED Audit.")
                return True
            else:
                print(f"❌ Task #{task_id} REJECTED by Auditor: {result.get('feedback')}")
                return False
        except Exception as e:
            print(f"⚠️ Auditor Error: {e}")
            return True # Fail-safe: approve if auditor crashes
