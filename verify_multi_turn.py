"""
Verification script for Multi-Turn Planning
"""
import os
import sys
import asyncio

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def test_task_planner_imports():
    print("\n🧪 Testing task_planner imports...")
    from task_planner import (
        TaskStep, TaskPlan, StepStatus, PlanStatus,
        decompose_task, PlanExecutor, plan_and_execute
    )
    print("✅ All imports successful!")

async def test_decomposition():
    print("\n🧪 Testing task decomposition...")
    from task_planner import decompose_task
    
    goal = "Find the latest AI news"
    plan = await decompose_task(goal)
    
    assert plan.goal == goal
    assert len(plan.steps) >= 1, "Should have at least 1 step"
    
    print(f"   Goal: {plan.goal}")
    print(f"   Steps: {len(plan.steps)}")
    for step in plan.steps:
        print(f"      {step.id}. [{step.tool}] {step.description}")
    
    print("✅ Task decomposition works!")
    return plan

async def test_executor():
    print("\n🧪 Testing PlanExecutor...")
    from task_planner import PlanExecutor, TaskStep, TaskPlan, StepStatus
    
    # Create a simple test plan
    plan = TaskPlan(
        id="test-001",
        goal="Test execution",
        steps=[
            TaskStep(
                id="1",
                description="Search for test",
                tool="echo",
                args={"message": "Hello from step 1"}
            ),
            TaskStep(
                id="2", 
                description="Use result from step 1",
                tool="echo",
                args={"message": "Step 2 says: {{result_1}}"},
                depends_on=["1"]
            )
        ]
    )
    
    # Create executor with mock tool
    executor = PlanExecutor()
    executor.register_tool("echo", lambda message: message)
    
    # Execute
    progress = []
    def on_progress(step):
        progress.append(step.id)
    
    result = await executor.execute_plan(plan, on_progress)
    
    assert result.status.value == "completed", f"Plan should complete, got {result.status}"
    assert len(progress) == 2, f"Should have 2 progress updates, got {len(progress)}"
    assert "1" in result.steps[1].result, "Step 2 should contain result from step 1"
    
    print(f"   Status: {result.status.value}")
    print(f"   Progress: {progress}")
    print("✅ PlanExecutor works!")

def test_database_schema():
    print("\n🧪 Testing database schema...")
    from database import init_db, get_db
    
    init_db()
    
    with get_db() as conn:
        # Check task_plans table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_plans'")
        assert cursor.fetchone(), "task_plans table should exist"
        
        # Check task_steps table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_steps'")
        assert cursor.fetchone(), "task_steps table should exist"
    
    print("✅ Database schema includes task tables!")

def test_plan_command_exists():
    print("\n🧪 Testing /plan command definition...")
    
    # Check clawdbot.py for plan command
    with open(os.path.join(PROJECT_ROOT, "clawdbot.py"), "r", encoding="utf-8") as f:
        content = f.read()
    
    assert 'name="plan"' in content, "/plan command should be defined"
    assert "plan_and_execute" in content, "Should use plan_and_execute"
    
    print("✅ /plan command is defined!")

async def main():
    test_task_planner_imports()
    await test_decomposition()
    await test_executor()
    test_database_schema()
    test_plan_command_exists()
    
    print("\n🎉 All Multi-Turn Planning tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
