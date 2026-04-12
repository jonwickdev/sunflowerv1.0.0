# Sunflower High-Command: The Global HQ is Open! 🌻🏢🚀

The construction is complete. Sunflower is no longer just a chatbot—she is a **CEO Orchestrator** managing a professional, scalable, and quality-assured workforce.

## 🏢 The New "Real Office" Structure

We have moved away from simple background scripts to a professional **Company Architecture**:

### 1. The Departments (Specialized Workforce)
Sunflower now has four dedicated "Expert Departments" each with its own **SOP (Standard Operating Procedure)**:
- **Research Dept**: Deep-web analysis, competitor audits, and niche discovery.
- **Marketing Dept**: Conversion-driven copy, social media strategy, and brand positioning.
- **Content Architects**: Human-like editorial production (blogs, newsletters, scripts).
- **General Ops**: Daily administration and basic coordination.

### 2. The Intern Model (Scaling to Swarms)
- **Sub-Agent Spawning**: When a mission is too large, the Department Head can spawn **Interns** (sub-tasks).
- **Concurrency**: Multiple agents now work in parallel. I've set a safe starting limit of **5 concurrent workers**, but this can be adjusted in your config for massive "Swarms."

### 3. The Master Calendar (Event-Driven Scheduler)
- **Non-Blocking Sleep**: Waiting for a 5am task no longer blocks other agents. The agent "frees its desk" and the Master Calendar wakes it up at exactly the right time.
- **Global Timezones**: Use `/timezone <City>` (e.g., `America/Chicago`) to tell Sunflower where you are. She handles all the clock math for you.

### 4. The Anti-Slop Auditor (Quality Control)
- **Analytical Critique**: Sunflower acts as your Chief Editor. She audits every report for "AI Slop" (generic fluff).
- **Auto-Redo**: If a report fails the quality test, Sunflower automatically sends it back for one internal redo to get more depth before bothering you.

---

## 🛠️ New Commands

- `/timezone <TZ>`: Set your current location (e.g., `/timezone America/Chicago`).
- `/schedule <frequency> <goal>`: Setup recurring missions (e.g., `/schedule daily Track AI news`).
- `/review <task_id>`: View the CEO's audit, depth score, and feedback for any task.

---

## 🚀 Deployment

Run these on your VPS to go live:
```bash
git pull
docker compose up -d --build
```

**Welcome to the High-Command.** 🌻🏗️🏢
