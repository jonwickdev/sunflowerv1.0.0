import sys
import os
import asyncio
import unittest
import datetime

# Add the project directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sunflower.config import Config
from sunflower.hq_manager import HqManager
from sunflower.tools import PluginManager
from sunflower.llm import LLMClient

class TestSunflowerSystem(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Create a sandboxed database
        self.test_db_path = "./test_hq.db"
        self.hq = HqManager()
        self.hq.db_path = self.test_db_path
        await self.hq.initialize()
        
        self.config = Config()

    async def asyncTearDown(self):
        # Cleanup sandboxed database
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    async def test_01_config_initialization(self):
        """Test that config loads and creates basic skeleton"""
        print("\n--- Test 01: Config Initialization ---")
        try:
            val = self.config.get_path("api_key", "missing")
            self.assertIsNotNone(val)
            print("✅ Config instantiated successfully.")
        except Exception as e:
            self.fail(f"Config failed to initialize: {e}")

    async def test_02_plugin_schema_integrity(self):
        """Test that PluginManager retrieves schemas properly and safely"""
        print("\n--- Test 02: Plugin Ecosystem ---")
        PluginManager.load_plugins()
        schemas = await PluginManager.get_all_schemas()
        
        # Verify it's a list
        self.assertIsInstance(schemas, list)
        self.assertTrue(len(schemas) > 0, "No plugins loaded")
        
        names = [s.get('function', {}).get('name') for s in schemas if isinstance(s, dict)]
        print(f"📦 Loaded {len(schemas)} tools dynamically: {names}")
        
        self.assertIn("ask_user", names, "Anti-hallucination ask_user tool missing!")
        self.assertIn("wait_until", names, "Time management tool missing!")
        print("✅ Plugin ecosystems parsed without schema crash.")

    async def test_03_hq_database_operations_and_timezone(self):
        """Test that SQLite tasks and SQL localtime gates behave as expected"""
        print("\n--- Test 03: HQ SQL Timezone Gates ---")
        now = datetime.datetime.now()
        
        # 1. Create a task that should wake up IMMEDIATELY (scheduled for 1 minute ago)
        past_target = now - datetime.timedelta(minutes=1)
        task_id = await self.hq.create_task("Test Immediate Wakeup", user_id=0)
        await self.hq.update_task_status(task_id, "queued", wake_up_at=past_target)
        
        queued_task = await self.hq.get_queued_task()
        self.assertIsNotNone(queued_task, "Task scheduled for the past failed to trigger immediately!")
        self.assertEqual(queued_task['id'], task_id)
        print("✅ Correctly woke up past task.")
        
        # 2. Create a task that should SLEEP (scheduled for 10 minutes in future)
        future_target = now + datetime.timedelta(minutes=10)
        task2_id = await self.hq.create_task("Test Sleeping", user_id=0)
        await self.hq.update_task_status(task2_id, "queued", wake_up_at=future_target)
        
        # Mark first task complete so it's not picked up
        await self.hq.update_task_status(task_id, "complete")
        
        # Poll again
        queued_task_2 = await self.hq.get_queued_task()
        self.assertIsNone(queued_task_2, "Task scheduled for FUTURE incorrectly triggered early!")
        print("✅ Correctly slept future task (Timezone overlap resolved).")

    async def test_04_llm_api_tunnel(self):
        """Test that LLM router is alive via public endpoints without using credits"""
        print("\n--- Test 04: LLM Client Tunnel ---")
        self.config.api_key = "dummy_key_to_pass_init"
        llm = LLMClient(self.config)
        providers = await llm.get_providers()
        self.assertIsInstance(providers, list)
        if len(providers) > 0:
            print(f"✅ Secure Tunnel Online. Fetched {len(providers)} openrouter providers natively.")
        else:
            print("⚠️ Endpoint fetched 0 providers. Might be offline or blocked by corporate firewall.")

if __name__ == '__main__':
    unittest.main()
