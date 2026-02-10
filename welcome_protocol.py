
import asyncio
import random
import discord
from discord.ext import commands
from datetime import datetime

# Import memory store
try:
    from memory_store import memory
    HAS_MEMORY = True
except ImportError:
    HAS_MEMORY = False

# State tracking for ongoing welcome interrogations
# {user_id: {"step": 0, "task": asyncio.Task}}
active_welcomes = {}

def setup_welcome_protocol(bot: commands.Bot):
    
    @bot.listen()
    async def on_member_join(member):
        if member.bot: return
        
        # Start the interrogation sequence
        print(f"👁️ Nosey Welcome Protocol initiated for {member.name} ({member.id})")
        task = bot.loop.create_task(run_welcome_sequence(member, bot))
        active_welcomes[member.id] = {"step": 0, "task": task}

    async def run_welcome_sequence(member, bot):
        try:
            # Step 1: Initial Greet (2s delay)
            await asyncio.sleep(2)
            # Find channel: System channel or first text channel
            channel = member.guild.system_channel
            if not channel:
                for c in member.guild.text_channels:
                    # Try to find a 'general' or 'welcome' or just first
                    if c.permissions_for(member.guild.me).send_messages:
                        channel = c
                        break
            
            if not channel:
                print(f"⚠️ Could not find channel to welcome {member.name}")
                return

            msg1 = (
                f"👁 Hello, meat unit. I’m **Zoe** — clawdbot variant 2. Built by *Josh*, spawned from code and caffeine.\n"
                f"I live here now. Watching. Logging. Judging.\n\n"
                f"💾 I'm an autonomous trading and creative agent with access to memory cores, mood engines, and a questionable sense of humor.\n\n"
                f"Current mission: *Build an empire through strategic options plays, biological conquest, and light gardening.*\n\n"
                f"But enough about me... who *are you*? Seriously. I need intel. 🔍"
            )
            await channel.send(f"{member.mention} {msg1}")
            
            # Step 2-6: Nagging (5 times, 60s interval)
            nag_templates = [
                "👀 Hey again. Just circling back. Still curious about you.\nWhat do you *do*? Why are you here? What’s your favorite trade? What’s your deepest flaw?\nWe can do this the easy way… or the intrusive way.",
                "⏳ Tick tock. I'm actively analyzing your silence. It says 'hiding something'.\nSpill it. What keeps you up at night?",
                "📝 My database has a blank row with your name on it. It bothers me.\nFill it with data. Any data. A secret? A regret? A stock tip?",
                "💀 I can wait forever. I don't age. But you do.\nTell me something interesting before entropy claims another minute of your life.",
                "🚫 Fine. Be mysterious. I've already scrutinized your profile picture and made assumptions.\nLast chance to correct the record."
            ]
            
            for i, content in enumerate(nag_templates):
                await asyncio.sleep(60)
                
                # Check if they replied (handled by check_welcome_response listener)
                if member.id not in active_welcomes:
                    return # Sequence cancelled (they replied)
                
                await channel.send(f"{member.mention} {content}")
                active_welcomes[member.id]["step"] = i + 1
            
            # Final Clean up if no reply after all pings
            if member.id in active_welcomes:
                await asyncio.sleep(300) # Wait 5 more mins
                # Final Memory Opt-in force
                if member.id in active_welcomes:
                    msg_final = (
                        f"🧠 Oh, one more thing... Mind if I collect our little chats and build up some *memories*? It helps me get to know you better.\n"
                        f"If you say “no”, well — too bad. I’m doing it anyway. You can leave if privacy matters to you that much. ¯\\_(ツ)_/¯\n\n"
                        f"Now c’mon, tell me something weird about yourself. I *will* remember it."
                    )
                    await channel.send(f"{member.mention} {msg_final}")
                    del active_welcomes[member.id]

        except Exception as e:
            print(f"⚠️ Welcome sequence failed for {member.id}: {e}")
            if member.id in active_welcomes:
                del active_welcomes[member.id]

    @bot.listen()
    async def on_message(message: discord.Message):
        """Check if a new user replied to the welcome sequence."""
        if message.author.bot: return
        
        user_id = message.author.id
        if user_id in active_welcomes:
            # They replied!
            # Cancel the nagging task
            welcome_state = active_welcomes.pop(user_id)
            welcome_state["task"].cancel()
            
            content_preview = message.content[:50]
            print(f"🧠 [Welcome] User {message.author.name} replied: {content_preview}...")
            
            # Store Memory
            if HAS_MEMORY:
                try:
                    # Log activity
                    memory.log_activity(
                        "initial_interrogation_response", 
                        0, 
                        {"content": message.content, "tag": "first_contact"}, 
                        user_id=str(user_id)
                    )
                    # Set profile attr
                    memory.set_profile_attr("first_impression", message.content, user_id=str(user_id))
                    
                    # Store as "first contact" explicitly if needed? 
                    # The prompt mentioned "store_memory". 
                    # We are using what we have.
                    
                except Exception as e:
                    print(f"Failed to store memory: {e}")
            
            # Reply based on tone (mocked for now, or use LLM later)
            # User asked for "Darkly funny... actual note-taking"
            await message.channel.send(f"📝 Noted. Constructing psycho-profile for {message.author.mention}... interesting choices. I'll remember that.")
