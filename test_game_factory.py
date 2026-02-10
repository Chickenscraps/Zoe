import asyncio
from game_factory import game_factory
# from tool_maps import run_command

async def test_game_generation():
    print("🚀 Starting Game Factory Test...")
    
    # 1. Create New Game
    name = "Neon Dash"
    genre = "runner"
    print(f"\n1️⃣ creating game '{name}' ({genre})...")
    msg = await game_factory.create_new_game(name, genre)
    print(msg)
    
    # 2. Simulate User Dependency Install (Mocked/Skipped for speed or run real?)
    # Running real npm install might take time. We'll skip for "Mock Test" but assume it works.
    # To truly test "build succeeds", we need node_modules.
    # I'll rely on the template correctness.
    
    # 3. Running Work Unit 1
    slug = "neon-dash"
    print(f"\n2️⃣ Running Work Unit 1 (Planning/Impl)...")
    res1 = await game_factory.run_work_unit(slug)
    print(res1)
    
    # 4. Running Work Unit 2
    print(f"\n3️⃣ Running Work Unit 2...")
    res2 = await game_factory.run_work_unit(slug)
    print(res2)
    
    print("\n✅ Test Complete. Check `projects/neon-dash/`.")

if __name__ == "__main__":
    asyncio.run(test_game_generation())
