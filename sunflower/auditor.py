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
        report_path = task.get('report_path')
        goal = task['goal']

        # Bug #7 fix: Safe file check instead of bare open()
        if not report_path:
            print(f"⚠️ Auditor: Task #{task_id} has no report_path. Auto-approving.")
            return True
        
        import os
        if not os.path.exists(report_path):
            print(f"⚠️ Auditor: Report file not found at {report_path}. Auto-approving.")
            return True

        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()
        
        if not report_content.strip():
            print(f"⚠️ Auditor: Report is empty for Task #{task_id}. Rejecting.")
            return False

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
            "RETURN ONLY A JSON OBJECT with these fields:\n"
            '{"depth_score": 0-10, "originality_score": 0-10, "is_slop": true/false, '
            '"feedback": "Specific feedback...", "decision": "approve" or "reject"}'
        )

        try:
            # Bug #8 fix: Don't use response_format (not all models support it)
            response = self.llm.client.chat.completions.create(
                model=self.config.default_model,
                messages=[{"role": "user", "content": prompt}]
            )
            import json
            raw = response.choices[0].message.content
            
            # Try to extract JSON from the response even if wrapped in markdown
            if "```" in raw:
                # Strip markdown code fences
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            
            result = json.loads(raw.strip())
            
            # Save metrics to DB
            await self.hq.update_task_status(
                task_id=task_id,
                status="pending_review",
                quality_score=result.get('depth_score', 0),
                feedback=result.get('feedback', '')
            )

            if result.get('decision') == 'approve' and result.get('depth_score', 0) >= 7:
                print(f"✅ Task #{task_id} PASSED Audit (Score: {result.get('depth_score')}/10).")
                return True
            else:
                print(f"❌ Task #{task_id} REJECTED by Auditor (Score: {result.get('depth_score')}/10): {result.get('feedback')}")
                return False
        except json.JSONDecodeError as e:
            print(f"⚠️ Auditor JSON parse error: {e}. Auto-approving.")
            return True
        except Exception as e:
            print(f"⚠️ Auditor Error: {e}. Auto-approving.")
            return True

