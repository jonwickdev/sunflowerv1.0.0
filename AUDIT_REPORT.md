# 🔴 Sunflower Code Audit Report
**Date:** 2026-04-11  
**Auditor:** Antigravity (Claude Opus 4.6)  
**Scope:** Every file modified or created in the "Global HQ v4.1" session

---

## Summary

I found **8 bugs**, of which **3 are crash-level** (will prevent the bot from starting or kill it mid-run). The rest are logic errors that would cause silent failures or wrong behavior.

---

## 🔴 CRASH-LEVEL BUGS (Bot won't start or dies mid-run)

### Bug #1: `Config.get()` does not exist → Worker crashes on startup
**File:** `worker.py`, lines 19 and 23  
**What I introduced:**
```python
self.semaphore = asyncio.Semaphore(config.get('max_concurrent_workers', 5))
```
**Why it crashes:** The `Config` class (in `config.py`) is a plain Python class. It does NOT have a `.get()` method — that's a `dict` method. This line throws `AttributeError: 'Config' object has no attribute 'get'` immediately when the bot starts.

**The fix:** Either add a `.get()` method to `Config`, or just use a hardcoded default:
```python
self.semaphore = asyncio.Semaphore(5)
```

---

### Bug #2: `generate_plan()` signature mismatch → Task execution crashes
**File:** `worker.py`, line 63 vs. line 169  
**What I introduced:**
```python
# Line 63 CALLS it with two args:
plan_content = await self.generate_plan(goal, dept)

# Line 169 DEFINES it with one arg:
async def generate_plan(self, goal: str) -> str:
```
**Why it crashes:** `generate_plan` is called with `dept` but the function signature only accepts `goal`. This throws `TypeError: generate_plan() takes 2 positional arguments but 3 were given` every time a task starts.

---

### Bug #3: `wait_until` tool blocks forever → Agent sits at desk, never frees it
**File:** `hq_plugin.py`, lines 54-55  
**What was already there (not fixed):**
```python
await asyncio.sleep(delay)  # If delay = 8 hours, this blocks for 8 hours
```
**Why it's broken:** The entire point of the "non-blocking wait" architecture is that agents should NOT sleep for hours. But the `wait_until` plugin still calls `asyncio.sleep(delay)` which blocks the agent's semaphore slot for the entire duration. The "free the desk" check in `worker.py` (line 116) looks for `"Sleeping"` in the result string, but the plugin returns `"Wake up!"` AFTER sleeping — so the worker never hits the early-return path.

**The real flow:**
1. Agent calls `wait_until("05:00")`
2. Plugin sleeps for 8 hours (BLOCKING the desk)
3. Plugin returns `"Wake up! It is now 05:00."`
4. Worker checks if `"Sleeping"` is in the result → it's NOT → desk stays occupied

---

## 🟠 LOGIC BUGS (Silent failures, wrong behavior)

### Bug #4: Double-finalize after auditor → Overwrites rejection with "complete"
**File:** `worker.py`, lines 146-167  
**What I introduced:** After the auditor logic (which correctly handles approve/reject), there is LEFTOVER code from the old version:
```python
# Lines 165-167 (OLD CODE, should have been deleted):
await self.hq.update_task_status(task_id, "complete")
await self.bot.send_message(user_id, f"✅ *Task #{task_id} Mission Accomplished!*...")
```
This runs AFTER the auditor's approve/reject block. So even if the auditor REJECTS a task and sets it to "queued" for a redo, this leftover code immediately overwrites it back to "complete" and sends a false "Mission Accomplished" message. **The auditor is completely bypassed.**

---

### Bug #5: `redo_count` is never incremented → Infinite redo loop
**File:** `worker.py`, lines 156-158  
**What I introduced:**
```python
redo_count = task.get('redo_count', 0)
if redo_count < 1:
    await self.hq.update_task_status(task_id, "queued")
```
The task is re-queued, but `redo_count` is never incremented in the database. It stays at 0 forever. The agent will be rejected and re-queued infinitely (or until Bug #4's leftover code "saves" it by marking everything complete).

---

### Bug #6: `InternPlugin` calls `hq.create_task()` without `initialize()`
**File:** `hq_plugin.py`, lines 137-140  
**What I introduced:**
```python
hq = HqManager()
new_id = await hq.create_task(...)
```
The `HqManager` requires `await hq.initialize()` before any database operation. The `DelegationPlugin` (line 27) correctly calls it, but the new `InternPlugin` and `SchedulerPlugin` do not. This will throw `sqlite3.OperationalError: no such table: tasks` if the DB hasn't been initialized by something else first.

---

### Bug #7: `auditor.py` uses bare `open()` without error handling
**File:** `auditor.py`, line 26  
**What I introduced:**
```python
if not report_path or not open(report_path).read().strip():
```
This opens a file handle but never closes it (no `with` statement). More critically, if `report_path` points to a file that doesn't exist yet (which happens if the agent crashes mid-run), this throws `FileNotFoundError` and the entire auditor crashes.

---

### Bug #8: `auditor.py` uses `response_format={"type": "json_object"}` — not supported by all models
**File:** `auditor.py`, line 57  
**What I introduced:**
```python
response_format={"type": "json_object"}
```
This parameter is only supported by certain OpenAI models and some OpenRouter models. If the user's `default_model` is set to a model that doesn't support `response_format` (like many open-source models on OpenRouter), this will throw an API error.

---

## 🟡 MINOR ISSUES

### Issue #9: `scheduler.py` creates its own `HqManager()` — duplicate DB connections
Both `bot.py` and `scheduler.py` and `worker.py` each create their own `HqManager()`. Since `aiosqlite` opens/closes connections per-call, this isn't a crash bug, but it means the DB is being initialized 3 separate times on startup.

### Issue #10: `_set_bot_commands()` lists 34 commands — Telegram limit is 100, but many are unimplemented
Most of the commands in the bot menu (compact, stop, fast, reasoning, elevated, etc.) are not implemented and will all hit the `unimplemented_command` catch-all. This is confusing for the user.

---

## 🔧 PRIORITY FIX ORDER

| Priority | Bug | Impact |
|----------|-----|--------|
| 1 | Bug #1 | Bot won't start at all |
| 2 | Bug #2 | Every task crashes |
| 3 | Bug #4 | Auditor is completely bypassed |
| 4 | Bug #3 | wait_until blocks forever, defeats the architecture |
| 5 | Bug #5 | Infinite redo loop |
| 6 | Bug #6 | Intern spawning crashes |
| 7 | Bug #7 | Auditor crashes on missing files |
| 8 | Bug #8 | Auditor crashes on some models |
