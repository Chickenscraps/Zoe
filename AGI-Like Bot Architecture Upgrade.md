# **GEMINI 3 DEEPTHINK — ARCHITECTURE \+ IMPLEMENTATION UPDATE**

## **1\. Reality Check & Corrections**

The transition from a reactive "chatbot" to a proactive, "AGI-like" agent within a local Windows 11 environment necessitates a rigorous audit of the current technical assumptions. The integration of OpenClaw (Node.js/TypeScript) with a custom Python-based agent (Clawdbot/Zoe) presents specific challenges regarding concurrency, operating system constraints, and the handling of real-time audio streams. This section deconstructs the provided technical breakdown against the realities of the specified hardware and software stack.

### **1.1 Concurrency and the "Split-Brain" Problem**

The prevailing assumption suggests running the OpenClaw Gateway alongside a custom Python bot potentially on the same Discord token or channel. This architecture introduces a critical "Split-Brain" conflict. Discord’s Gateway Protocol generally enforces a single WebSocket connection per shard for a bot token.1 Attempting to have two distinct processes—the Node.js Gateway and the Python Zoe process—simultaneously negotiate the same Gateway connection for the same bot user will result in "Identify" race conditions, disconnection loops, and state desynchronization.

While OpenClaw serves as an excellent infrastructure layer for generic message routing and skill management 3, it operates primarily as a text-based message router.5 It lacks the native, low-level access to UDP voice packets required for high-performance, real-time audio processing.6 To achieve "AGI-like" voice interaction—characterized by sub-second latency, effective interruption handling, and speaker separation—the Python process must hold the authoritative connection to the Discord Voice Gateway. Routing raw PCM audio data through the Node.js Gateway via WebSockets to the Python agent for processing would introduce unacceptable latency (likely exceeding 500ms), degrading the user experience from conversational to transactional.8

### **1.2 Windows 11 Constraint Analysis**

The requirement for "local-first" execution on Windows 11 introduces operational constraints distinct from Linux-based server environments.

**Service Isolation (Session 0):** The requirement for "Tool-first" execution involves controlling the browser and OS files.10 On Windows, background services run in "Session 0," which is isolated from the user's interactive desktop. If the agent is deployed as a standard Windows Service (e.g., via NSSM), it will be unable to interact with GUI elements or launch visible browser windows for debugging artifacts. Therefore, the agent must run within the active user session, managed via a user-level daemon or startup script, rather than a system-level service.12

**Audio Subsystem:** Unlike Linux’s PulseAudio or ALSA, Windows relies on WASAPI. While discord.py handles the transmission of audio frames effectively, capturing system audio (if the agent needs to "hear" the PC itself) or ensuring stable long-term voice connections requires careful management of the FFmpeg binaries, which must be manually installed and added to the system PATH, as they are not included in standard Python package installations.13

**Model Concurrency:** Running Ollama (Llama 3.x), Faster-Whisper (STT), and Edge-TTS simultaneously on a consumer-grade Windows machine creates significant VRAM and compute pressure. Without strict resource locking (serializing "Listening" \-\> "Thinking" \-\> "Speaking"), the system risks Out-Of-Memory (OOM) crashes or "hanging" behavior where the bot appears deaf while processing a thought.15

### **1.3 The "Admin Gate" Fallacy**

The assumption that a "Root Admin Gate" can be implemented via simple string matching or LLM self-regulation is structurally unsound. LLMs are non-deterministic; a request to "delete a file" might materialize as os.remove, shutil.rmtree, or a custom shell command.17 Relying on the model to "ask for permission" is a safety failure mode known as "Instruction Drift".18

**Correction:** The safety layer must be implemented as **Middleware Code** that intercepts the structured tool call *before* execution. It must validate the intent against a rigid schema, independent of the LLM's "reasoning," and enforce the approval workflow via the Discord UI.19

### **1.4 Dependencies and Code-Level Gotchas**

* **VAD (Voice Activity Detection):** Standard discord.py receive capability is raw. Without a robust VAD filter (like webrtcvad or silero-vad), the agent will transcribe keyboard clicks, breathing, and background noise, leading to hallucinated responses.6  
* **Dependency Conflicts:** The Python environment must carefully manage versions between discord.py (which uses asyncio) and synchronous processing libraries. The use of nest\_asyncio or rigorous separation of blocking calls (like database writes or heavy inference) to thread pools is mandatory to prevent the bot from "freezing" (heartbeat timeout) during heavy cognitive loads.6  
* **File Locking:** Windows is aggressive about file locking. If the agent attempts to read a log file that another process (like a game or the OS) is writing to, it will crash with PermissionError. Retries with exponential backoff are required for all file I/O operations.22

## ---

**2\. Architecture vNext**

### **2.1 The Architectural Decision: Sidecar Model**

To resolve the conflict between the OpenClaw Gateway and the custom Zoe Agent, we evaluate two primary integration patterns.

**Option A: Integrated (Gateway Plugin)**

In this model, the Python logic runs as a downstream plugin to the OpenClaw Node.js process. The Gateway handles the Discord connection and forwards events to Python via HTTP/WebSocket.

* *Pros:* Centralized configuration.  
* *Cons:* High latency for voice; loss of fine-grained control over Discord API events (like Voice State Updates); dependency on OpenClaw's update cycle.

**Option B: Sidecar (Parallel Execution) \- RECOMMENDED**

In this model, the Python Agent ("Zoe") acts as the primary "Brain" and owns the Discord connection directly. The OpenClaw Gateway runs in parallel as a "Utility Server" or "Tool Provider" but does not manage the Discord bot user directly.

* *Rationale:* This decoupling allows the Python agent to utilize discord.py's native support for UDP voice traffic 6, ensuring the low latency required for "AGI-like" conversation. It also allows the agent to leverage the rich Python ecosystem for AI (Ollama, PyTorch, Pandas) without serialization overhead.

### **2.2 System Diagram**

The following Mermaid diagram illustrates the recommended **Sidecar Architecture**, where the Zoe Agent (Python) is the central orchestrator, interfacing directly with the user and the OS, while treating the OpenClaw Gateway as a resource.

Code snippet

graph TD  
    %% Subsystems Definition  
    subgraph "Windows 11 Host Environment"  
        direction TB

        subgraph "Zoe Core (Python 3.10+)"  
            EventLoop\[Main Event Loop (Asyncio)\]  
            Scheduler  
            State  
              
            EventLoop \--\>|Polls| Scheduler  
            EventLoop \--\>|Updates| State  
        end  
          
        subgraph "Senses & IO Layer"  
            DiscordPy  
            VoiceEngine  
            TTS  
              
            DiscordPy \<--\>|WSS Events| EventLoop  
            DiscordPy \<--\>|UDP Audio| VoiceEngine  
            VoiceEngine \--\>|Transcribed Text| EventLoop  
            EventLoop \--\>|Reply Audio| TTS \--\>|Stream| DiscordPy  
        end  
          
        subgraph "Cognition & Memory Layer"  
            Ollama\[Ollama (Llama 3.1)\]  
            Gemini  
            SQLite  
            VecDB  
              
            EventLoop \<--\>|Inference| Ollama  
            Ollama \-.-\>|Fallback| Gemini  
            EventLoop \<--\>|RAG| VecDB  
            EventLoop \<--\>|Logs/Profiles| SQLite  
        end  
          
        subgraph "Action & Safety Layer"  
            Gate\[Approval Middleware\]  
            Tools  
            OS  
            OpenClaw\[OpenClaw Gateway (Localhost)\]

            EventLoop \--\>|Tool Request| Gate  
            Gate \--\>|Risk: HIGH| DiscordPy  
            Gate \--\>|Risk: LOW / Approved| Tools  
            Tools \--\>|Execute| OS  
            Tools \-.-\>|Request Skill| OpenClaw  
        end  
    end  
      
    %% External Interactions  
    User((Users)) \<--\>|Discord Client| DiscordPy  
    Admin((CHICKENSCRAPS)) \-.-\>|Approve Action| DiscordPy

### **2.3 Modules and Responsibilities**

**1\. The Mainframe (main.py)** This is the entry point and daemon process. It initializes the discord.Bot instance, establishes the SQLite connection, and starts the APScheduler background threads. It handles the "Hot Reload" logic by monitoring file changes via watchdog and restarting the internal loops if code is updated.23

**2\. The Cognition Engine (cortex.py)** This module wraps the LLM interactions. It manages the context window, injecting the "Zoe" persona, current mood state, and retrieved memories into the system prompt. It handles the fallback logic: if Ollama times out or returns incoherent output, it escalates the request to the Gemini API for "Deep Reasoning".15

**3\. The Interface Layer (interface/)**

* discord\_client.py: Manages the WebSocket connection and text events.  
* voice\_client.py: Manages the UDP connection, implementing the AudioSink for receiving and the AudioSource for streaming TTS.21

**4\. The Safety Middleware (safety.py)** This module implements the "Approval Gate." It intercepts every tool execution request, classifies it against a RISK\_REGISTRY, and creates the interactive Discord components (Buttons) for administrator authorization.19

### **2.4 Interfaces and Contracts**

**Event Contract (Internal):**

JSON

{  
  "event\_type": "MESSAGE\_CREATE",  
  "timestamp": "2026-02-08T14:00:00Z",  
  "author": {"id": 12345, "name": "Ben", "role": "admin"},  
  "content": "Zoe, delete the temp logs.",  
  "channel\_id": 1174052382057963623,  
  "context": {"voice\_active": true, "mood": "focused"}  
}

**Tool Execution Schema (Output):**

JSON

{  
  "tool": "fs\_delete\_file",  
  "arguments": {"path": "C:\\\\Temp\\\\logs.txt"},  
  "reasoning": "User requested cleanup of temporary files.",  
  "risk\_level": "HIGH"  
}

### **2.5 Daemon and Restart Strategy**

To maintain "Always-On" presence on Windows 11:

1. **Daemon Script:** A PowerShell script or Batch file (start\_zoe.bat) that runs python main.py in a loop. If the Python process exits (crash or reload), the script waits 5 seconds and restarts it.  
2. **Startup:** This script is placed in the Windows Startup folder (shell:startup) to ensure the agent launches on user login.  
3. **Hot Reload:** The Python application uses watchdog to monitor its own source directory. Upon detecting a .py file change, it performs a graceful shutdown (saving state to SQLite) and exits with a specific status code, prompting the wrapper script to restart it instantly.28

## ---

**3\. AGI-Like Behavior Engine**

True "AGI-like" behavior stems from the illusion of independent agency. This is achieved not through magic, but through concurrent processing loops that allow the agent to act without direct external stimulus.

### **3.1 The Event-Driven Loop (The Reflex)**

This loop handles immediate, reactive interactions. It operates on the millisecond scale.

* **Triggers:** Discord Message, Voice Activity (VAD trigger), User Presence Update (Join/Leave).  
* **Logic:**  
  1. **Perceive:** Decode the input (Text or STT).  
  2. **Contextualize:** Query Short-Term Memory and Vector Store for relevance.  
  3. **Decide:** Determine if a response is required. (e.g., Is the user talking to me? Is the silence awkward?).  
  4. **Act:** Generate response, execute tool, or update internal state (e.g., "User is angry").

### **3.2 The Scheduler Loop (The Bio-Rhythm)**

Implemented via APScheduler, this loop gives Zoe a sense of time and purpose, simulating a circadian rhythm.23

| Time | Task | Description |
| :---- | :---- | :---- |
| **08:00** | morning\_brief | Scrape news, check system logs, compile "Sitrep", and post to \#general. |
| **09:00-18:00** | work\_mode | Passive monitoring. Only interrupt for high-priority alerts (Market crashes, Server errors). |
| **02:00** | night\_shift | "Deep Work" mode. Clean database, summarize daily logs, perform long-running research tasks.29 |
| **Every 1h** | novelty\_check | Poll external feeds (News, Github) for high-relevance items to share. |

**Anti-Spam Logic:** The Scheduler employs "Cadence Gates." Before posting a proactive nudge, it checks the last\_message\_timestamp for the channel. If \< 30 mins, it suppresses the nudge to avoid interrupting active human conversations.2

### **3.3 The Task Execution Loop (The Hands)**

Complex tasks are decoupled from the chat loop to prevent blocking.

1. **Plan:** The LLM decomposes a request ("Research X") into a DAG (Directed Acyclic Graph) of steps.  
2. **Queue:** Steps are pushed to a generic TaskQueue in SQLite.  
3. **Execute:** A background worker picks up tasks, executes them (e.g., browser.scrape), and stores the artifact.  
4. **Report:** Upon completion, the agent receives a TASK\_COMPLETE event and notifies the user.10

### **3.4 The Novelty Engine**

To prevent robotic staleness, Zoe utilizes a "Novelty Engine" that injects non-sequiturs or relevant updates based on a probabilistic model.

* **Algorithm:**  
  * P(Speak) \= Base\_Chance \+ Relevance\_Score \- Recency\_Penalty.  
  * **Relevance:** Derived from cosine similarity between the news item embedding and the User Profile embedding.  
  * **Effect:** If a massive piece of gaming news drops (e.g., "GTA6 Trailer"), the Relevance Score spikes, overcoming the Recency Penalty, causing Zoe to "barge in" with the news.32

## ---

**4\. Memory \+ Mood System (Production-Grade)**

The "Brain" relies on a structured schema to manage identity, history, and emotional state, moving beyond simple JSON dumps to a relational model capable of complex queries.

### **4.1 Data Model (SQLite Schema)**

**Table: user\_profiles** Stores long-term traits and permissions.22

| Column | Type | Notes |
| :---- | :---- | :---- |
| discord\_id | INTEGER | Primary Key. |
| username | TEXT | Current display name. |
| trust\_level | INTEGER | 0=Guest, 1=User, 10=Root (CHICKENSCRAPS). |
| opt\_in\_voice | BOOLEAN | Consent for recording.33 |
| opt\_in\_romance | BOOLEAN | Consent for flirty persona.34 |
| interests | JSON | \["gaming", "crypto", "AI"\]. |
| voice\_print | BLOB | Embedding for speaker ID (Future Phase). |

**Table: memory\_items (Episodic & Semantic)** Combines logs with vector embeddings for RAG.35

| Column | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER | Primary Key. |
| user\_id | INTEGER | Foreign Key to user\_profiles. |
| content | TEXT | The memory content. |
| embedding | BLOB | 1536d vector (from Ollama/nomic-embed). |
| type | TEXT | "CONVERSATION", "FACT", "SUMMARY". |
| timestamp | DATETIME | ISO8601. |

**Table: mood\_log** Tracks the agent's emotional trajectory.36

| Column | Type | Notes |
| :---- | :---- | :---- |
| timestamp | DATETIME |  |
| valence | FLOAT | \-1.0 (Negative) to 1.0 (Positive). |
| arousal | FLOAT | 0.0 (Calm) to 1.0 (Excited). |
| dominance | FLOAT | 0.0 (Submissive) to 1.0 (Dominant). |
| trigger | TEXT | Reason for change ("User compliment"). |

### **4.2 Retrieval Pipeline**

1. **User ID Resolution:** Identify the speaker via Discord ID or Voice SSRC.  
2. **Context Assembly:**  
   * Fetch user\_profiles data.  
   * Fetch last 10 memory\_items (Episodic).  
   * **Vector Search:** Query memory\_items using the current input embedding to find semantically related past discussions (Semantic).37  
3. **Mood Injection:**  
   * Read latest mood\_log.  
   * If valence \> 0.5 and opt\_in\_romance is True, inject "Playful/Flirty" into the system prompt.  
   * If valence \< \-0.2, inject "Curt/Professional" tone.

### **4.3 Privacy & Deletion**

To respect privacy constraints:

* **Command:** \!forget \[last|all\].  
* **Workflow:**  
  * last: Deletes the most recent entry in memory\_items for that user.  
  * all: Deletes all rows in memory\_items where user\_id matches, requiring an explicit confirmation step ("Are you sure? Type 'CONFIRM'").  
* **No-Training Guarantee:** The system explicitly tags data as "Retrieval Only." No fine-tuning scripts are included in the architecture.3

## ---

**5\. Voice System**

The voice system is the most technically demanding component on Windows 11\. It must handle the full cycle of Hearing \-\> Understanding \-\> Thinking \-\> Speaking \-\> Stopping (Interrupting).

### **5.1 STT Pipeline (The Ears)**

Direct access to Discord's UDP audio stream is required.

1. **Audio Sink:** We implement a custom AudioSink class in discord.py using discord-ext-voice-recv. This intercepts incoming Opus packets, decodes them to PCM (Pulse Code Modulation).6  
2. **Demuxing:** Discord sends audio mixed or as separate streams per user (SSRC). We map SSRC to User ID to support multi-speaker transcription.  
3. **VAD Gating:** To prevent processing silence, we use webrtcvad.  
   * Incoming PCM data is chunked into 30ms frames.  
   * Frames are fed to the VAD. If is\_speech() is true, they are buffered.  
   * **Silence Threshold:** If silence persists for \> 500ms, the buffer is committed.  
4. **Transcription:** The buffer is sent to Faster-Whisper (running locally on GPU/CPU). It returns text.38

### **5.2 TTS Pipeline (The Voice)**

Zoe needs a voice that matches her persona (37, Elite Operator).

1. **Engine:** We utilize edge-tts (Microsoft Edge Online TTS). It offers high-quality "Neural" voices (e.g., en-US-AvaNeural) without the heavy compute cost of local Coqui TTS.6  
2. **Synthesis:** The LLM's text response is sent to the Edge API, which returns an MP3 stream.  
3. **Playback:** The MP3 is converted to PCM on-the-fly using FFmpeg and streamed to the Discord Voice Client.

### **5.3 Interruptibility (The "Barge-In")**

"AGI-like" feel requires the ability to be interrupted.

* **Mechanism:** The AudioSink remains active *while* the bot is speaking.  
* **Logic:** If the VAD detects strong speech input from a user (ignoring the bot's own audio loopback) while voice\_client.is\_playing() is true:  
  1. **Stop:** Immediately call voice\_client.stop().  
  2. **Listen:** Clear the TTS queue and focus on the new input.  
  3. **Acknowledge:** (Optional) append "\[Interrupted\]" to the conversation log.

### **5.4 Join/Leave State Machine**

**Target Channel:** 1174052382057963623\.

* **Auto-Join:** The on\_voice\_state\_update event listener checks if a user joins the target channel. If len(members) \== 1 (first user), Zoe connects.39  
* **Auto-Leave:** If len(members) \== 1 (only Zoe is left), she starts a 30-second timer. If no one joins, she disconnects to save resources.

## ---

**6\. ApprovalGate & Safety Middleware**

The "Root Admin Gate" is the system's failsafe. It operates at the code level, intercepting tool calls before they reach the OS.

### **6.1 Risk Classification Rubric**

Every tool in the library is assigned a static risk level.27

| Risk Level | Definition | Examples | Handling |
| :---- | :---- | :---- | :---- |
| **LOW** | Read-only, Information retrieval. | time\_get, weather\_check, memory\_recall. | Auto-Execute. |
| **MED** | External read, Browser access. | google\_search, read\_file, polymarket\_fetch. | Auto-Execute (Log to Audit). |
| **HIGH** | Write access, System modification. | write\_file, install\_pip, move\_file. | **Approval Required.** |
| **CRITICAL** | Destructive, Admin privileges. | delete\_file, os\_system, firewall\_change. | **Root Admin Only.** |

### **6.2 The Gatekeeper Logic**

When the Cognition Engine selects a tool:

1. **Intercept:** The SafetyMiddleware class receives the tool name and arguments.  
2. **Classify:** Look up the tool in the RISK\_REGISTRY.  
3. **Enforce:**  
   * If **LOW/MED**: Allow execution.  
   * If **HIGH/CRITICAL**:  
     * Check if user.id \== CHICKENSCRAPS.  
     * If not Admin and risk is CRITICAL: **Deny immediately**.  
     * Otherwise: **Pause execution** and trigger the Approval Workflow.

### **6.3 Discord Approval Workflow**

1. **Prompt:** Zoe sends a Discord Message with a specific Embed ("⚠️ Authorization Required").  
2. **Payload:** The embed details the Action, Target (e.g., file path), and Reasoning.  
3. **Interaction:** The message includes two buttons: and.  
4. **Callback:**  
   * The bot waits asynchronously for a button press.  
   * It validates that the clicker is the authorized Admin.42  
   * On Approval: The tool executes.  
   * On Denial: The tool throws a PermissionDenied error back to the LLM.

### **6.4 Audit Logging**

Every gated action generates an immutable log entry in audit.csv:

ISO\_TIMESTAMP | USER\_ID | TOOL | ARGS | RISK | OUTCOME | APPROVER\_ID

## ---

**7\. World Context: News \+ Weather**

To fulfill the "One of the boys" persona, Zoe must bring relevant world information to the group without being prompted.

### **7.1 Source Integration**

* **News:** Python feedparser ingests RSS feeds from curated sources:  
  * *Gaming:* IGN, Kotaku, Reddit (r/Games JSON).  
  * *AI:* HackerNews, Arxiv Sanity.  
  * *Markets:* Yahoo Finance API, Polymarket Gamma API.43  
* **Weather:** Open-Meteo API (Free, no key required).

### **7.2 The "Wild but Relevant" Algorithm**

1. **Fetch:** Every hour, pull the latest headers from all sources.  
2. **Filter:** Discard items older than 2 hours.  
3. **Score:** Calculate a "Relevance Score" based on User Interests.  
   * If title contains "GTA6" and user\_interests includes "Gaming", Score \+= 10\.  
4. **Threshold:** If Score \> 8 (High Relevance), trigger a notification.  
5. **Refine:** Pass the headline to the LLM with the prompt: *"Rewrite this headline to be casual, cynical, or hyped, depending on the content. Keep it under 20 words."*.44

### **7.3 Output Templates**

* **Standard Nudge:**"Yo, did you see this? Valve just nerfed the AWP again. \[Link\]"  
* **Morning Brief (Section):Markets:** Crypto is down bad. ETH at $2200.  
  **Weather:** 72°F in LA. Touch grass.  
  **Wild Card:** Someone made Doom run on a bacteria. Not joking. \[Link\]

## ---

**8\. Phased Implementation Plan**

### **Phase 0: The Foundation (Week 1\)**

* **Goal:** Stability and Safety.  
* **Modules:** main.py, safety.py, discord\_client.py, config.yaml.  
* **Tasks:**  
  1. Setup Python environment and requirements.txt.  
  2. Implement the Discord Bot connection.  
  3. Implement the ApprovalGate middleware and Discord Buttons.  
  4. Verify that CHICKENSCRAPS can approve actions, and others are blocked.  
* **Test Plan:** Attempt to run a dummy "delete file" command from a non-admin account. Verify blockage.

### **Phase 1: The Senses (Week 2\)**

* **Goal:** Hearing and Remembering.  
* **Modules:** voice\_client.py, cortex.py (Memory), SQLite DB.  
* **Tasks:**  
  1. Implement AudioSink and VAD logic.  
  2. Connect Faster-Whisper and Edge-TTS.  
  3. Implement the \!consent command for Voice Opt-in.  
  4. Build the SQLite schema (users, memories).  
* **Test Plan:** Join voice, speak a sentence, verify transcription in logs. Verify TTS reply.

### **Phase 2: Agency & Rhythm (Week 3\)**

* **Goal:** Work and Time.  
* **Modules:** scheduler.py, tools/ (Filesystem, Browser), Polymarket API.  
* **Tasks:**  
  1. Configure APScheduler for the 8 AM Morning Brief.  
  2. Implement the "Night Shift" logic (Log summarization).  
  3. Build the Tool Library (File I/O, Web Search).  
  4. Integrate Polymarket Gamma API (Read-only research).  
* **Test Plan:** Trigger the Morning Brief manually. Verify it generates a valid Markdown artifact.

### **Phase 3: Persona & Novelty (Week 4\)**

* **Goal:** "Zoe" comes alive.  
* **Modules:** novelty.py, mood.py.  
* **Tasks:**  
  1. Implement the "Wild but Relevant" news algorithm.  
  2. Refine the System Prompt with the "Elite Operator" persona nuances.  
  3. Add the Romance/Flirt toggle logic in the Mood system.  
* **Test Plan:** Run the bot for 24 hours. Check for at least one relevant, unprompted news nudge.

## ---

**9\. Concrete Next Actions (Top 20\)**

1. **\[Env\]** Install Python 3.10 and FFmpeg on the Windows 11 host. Ensure FFmpeg is in the System PATH.  
2. \*\*\*\* Create a new Discord Application. Enable "Message Content" and "Server Members" intents.  
3. \*\*\*\* Initialize clawd-zoe repository. Create requirements.txt (discord.py, faster-whisper, peewee, apscheduler, edge-tts).  
4. **\[Config\]** Create config.yaml. Add DISCORD\_TOKEN, CHICKENSCRAPS\_ID, and VOICE\_CHANNEL\_ID.  
5. \*\*\*\* Write db\_init.py to initialize the SQLite database with users, memories, and audit\_log tables.  
6. \*\*\*\* Write main.py. Implement basic connection logic and the on\_ready event.  
7. \*\*\*\* Implement class ApprovalGate. Define the RISK\_REGISTRY dictionary.  
8. **\[UI\]** Create the ApprovalView class (Discord Buttons) for the safety gate.  
9. **\[Logic\]** Implement cortex.py. Set up the Ollama API wrapper and System Prompt injection.  
10. **\[Voice\]** Install discord-ext-voice-recv. Implement BasicSink to test audio capture.  
11. **\[Voice\]** Implement VAD logic (webrtcvad) to filter silence from the audio stream.  
12. **\[Voice\]** Integreate Faster-Whisper. Create a function that accepts PCM buffer and returns text.  
13. **\[Voice\]** Implement EdgeTTS wrapper. Create a speak(text) function that streams audio to Discord.  
14. **\[Voice\]** Write the auto\_join logic for channel 1174... on user join.  
15. \*\*\*\* Create tools/system.py. Implement safe read\_file and gated write\_file functions.  
16. \*\*\*\* Initialize APScheduler in main.py. specific a dummy job to print "Tick" every minute.  
17. **\[News\]** Write news\_fetcher.py. Implement RSS parsing for HackerNews.  
18. **\[Privacy\]** Implement \!forget command to clear user memory rows.  
19. \*\*\*\* Create start\_zoe.bat loop script for Windows auto-restart.  
20. \*\*\*\* Execute a full integration test: User speaks \-\> Text transcribed \-\> LLM processes \-\> Tool checked \-\> Audio reply generated.

#### **Works cited**

1. Build a Discord Bot with Node.js | Codecademy, accessed February 8, 2026, [https://www.codecademy.com/article/build-a-discord-bot-with-node-js](https://www.codecademy.com/article/build-a-discord-bot-with-node-js)  
2. How To Build a Discord Bot with Node.js \- DigitalOcean, accessed February 8, 2026, [https://www.digitalocean.com/community/tutorials/how-to-build-a-discord-bot-with-node-js](https://www.digitalocean.com/community/tutorials/how-to-build-a-discord-bot-with-node-js)  
3. What is OpenClaw? Your Open-Source AI Assistant for 2026 | DigitalOcean, accessed February 8, 2026, [https://www.digitalocean.com/resources/articles/what-is-openclaw](https://www.digitalocean.com/resources/articles/what-is-openclaw)  
4. The awesome collection of OpenClaw Skills. Formerly known as Moltbot, originally Clawdbot. \- GitHub, accessed February 8, 2026, [https://github.com/VoltAgent/awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills)  
5. OpenClaw \- OpenClaw, accessed February 8, 2026, [https://docs.openclaw.ai/](https://docs.openclaw.ai/)  
6. Real-time Discord STT Bot using Multiprocessing & Faster-Whisper : r/Python \- Reddit, accessed February 8, 2026, [https://www.reddit.com/r/Python/comments/1p211nn/realtime\_discord\_stt\_bot\_using\_multiprocessing/](https://www.reddit.com/r/Python/comments/1p211nn/realtime_discord_stt_bot_using_multiprocessing/)  
7. Discord Bot with OpenAI Whisper Integration \- Inconsistent Transcription \- Stack Overflow, accessed February 8, 2026, [https://stackoverflow.com/questions/77707085/discord-bot-with-openai-whisper-integration-inconsistent-transcription](https://stackoverflow.com/questions/77707085/discord-bot-with-openai-whisper-integration-inconsistent-transcription)  
8. Connecting OSX app to remote, GUI is very unhelpful \- Friends of the Crustacean, accessed February 8, 2026, [https://www.answeroverflow.com/m/1467370025722839136](https://www.answeroverflow.com/m/1467370025722839136)  
9. Cap'n Web: a new RPC system for browsers and web servers \- The Cloudflare Blog, accessed February 8, 2026, [https://blog.cloudflare.com/capnweb-javascript-rpc-library/](https://blog.cloudflare.com/capnweb-javascript-rpc-library/)  
10. Playwright Test Agents, accessed February 8, 2026, [https://playwright.dev/docs/test-agents](https://playwright.dev/docs/test-agents)  
11. Welcome to PyAutoGUI's documentation\! — PyAutoGUI documentation, accessed February 8, 2026, [https://pyautogui.readthedocs.io/](https://pyautogui.readthedocs.io/)  
12. Python to control windows : r/learnpython \- Reddit, accessed February 8, 2026, [https://www.reddit.com/r/learnpython/comments/14wx9a1/python\_to\_control\_windows/](https://www.reddit.com/r/learnpython/comments/14wx9a1/python_to_control_windows/)  
13. openai/whisper: Robust Speech Recognition via Large-Scale Weak Supervision \- GitHub, accessed February 8, 2026, [https://github.com/openai/whisper](https://github.com/openai/whisper)  
14. How to Install & Use Whisper AI Voice to Text \- YouTube, accessed February 8, 2026, [https://www.youtube.com/watch?v=ABFqbY\_rmEk](https://www.youtube.com/watch?v=ABFqbY_rmEk)  
15. Running OpenClaw Without Burning Money, Quotas, or Your Sanity \- GitHub Gist, accessed February 8, 2026, [https://gist.github.com/digitalknk/ec360aab27ca47cb4106a183b2c25a98](https://gist.github.com/digitalknk/ec360aab27ca47cb4106a183b2c25a98)  
16. Automatic Speech Recognition Using OpenAI Whisper without a GPU | by Benjamin Consolvo | Intel Analytics Software | Medium, accessed February 8, 2026, [https://medium.com/intel-analytics-software/automatic-speech-recognition-using-openai-whisper-without-a-gpu-9d316a93860a](https://medium.com/intel-analytics-software/automatic-speech-recognition-using-openai-whisper-without-a-gpu-9d316a93860a)  
17. Comprehensive Guide to User Input Simulation on Any Device \- Adapta Robotics, accessed February 8, 2026, [https://www.adaptarobotics.com/blog/comprehensive-guide-to-user-input-simulation-on-any-device/](https://www.adaptarobotics.com/blog/comprehensive-guide-to-user-input-simulation-on-any-device/)  
18. From magic to malware: How OpenClaw's agent skills become an attack surface, accessed February 8, 2026, [https://1password.com/blog/from-magic-to-malware-how-openclaws-agent-skills-become-an-attack-surface](https://1password.com/blog/from-magic-to-malware-how-openclaws-agent-skills-become-an-attack-surface)  
19. Technical How-to – Artificial Intelligence \- AWS \- Amazon.com, accessed February 8, 2026, [https://aws.amazon.com/blogs/machine-learning/category/post-types/technical-how-to/feed/](https://aws.amazon.com/blogs/machine-learning/category/post-types/technical-how-to/feed/)  
20. accessed February 8, 2026, [https://trigger.dev/docs/llms-full.txt](https://trigger.dev/docs/llms-full.txt)  
21. How to log user's leave and join time to a voice channel in discord.py? \- Stack Overflow, accessed February 8, 2026, [https://stackoverflow.com/questions/67410329/how-to-log-users-leave-and-join-time-to-a-voice-channel-in-discord-py](https://stackoverflow.com/questions/67410329/how-to-log-users-leave-and-join-time-to-a-voice-channel-in-discord-py)  
22. Building Memory in AI Agents: Design Patterns and Datastores That Enable Long-Term Intelligence \- Trixly AI Solutions, accessed February 8, 2026, [https://www.trixlyai.com/blog/technical-14/building-memory-in-ai-agents-design-patterns-and-datastores-that-enable-long-term-intelligence-87](https://www.trixlyai.com/blog/technical-14/building-memory-in-ai-agents-design-patterns-and-datastores-that-enable-long-term-intelligence-87)  
23. Ultimate guide to Celery library in Python \- Deepnote, accessed February 8, 2026, [https://deepnote.com/blog/ultimate-guide-to-celery-library-in-python](https://deepnote.com/blog/ultimate-guide-to-celery-library-in-python)  
24. How to Build a Labubu Bot with Residential Proxies: Step-by-Step Guide \- Decodo, accessed February 8, 2026, [https://decodo.com/blog/how-to-build-a-labubu-bot](https://decodo.com/blog/how-to-build-a-labubu-bot)  
25. How to Integrate Local LLMs With Ollama and Python, accessed February 8, 2026, [https://realpython.com/ollama-python/](https://realpython.com/ollama-python/)  
26. Im trying to make a simple discord bot that joins and leaves a voice channel, but I cant make the bot leave the channel \- Stack Overflow, accessed February 8, 2026, [https://stackoverflow.com/questions/67541272/im-trying-to-make-a-simple-discord-bot-that-joins-and-leaves-a-voice-channel-bu](https://stackoverflow.com/questions/67541272/im-trying-to-make-a-simple-discord-bot-that-joins-and-leaves-a-voice-channel-bu)  
27. Understanding Risk Management for AI Agents | Galileo, accessed February 8, 2026, [https://galileo.ai/blog/risk-management-ai-agents](https://galileo.ai/blog/risk-management-ai-agents)  
28. timolins/clawdbot: Your own personal AI assistant. Any OS. Any Platform. \- GitHub, accessed February 8, 2026, [https://github.com/timolins/clawdbot](https://github.com/timolins/clawdbot)  
29. Overnight support for SaaS companies: AI as the night shift \- Crisp, accessed February 8, 2026, [https://crisp.chat/en/blog/overnight-support-for-saas-companies-ai-as-the-night-shift/](https://crisp.chat/en/blog/overnight-support-for-saas-companies-ai-as-the-night-shift/)  
30. Self-Evolving Agent Build Day \- AGI House Events, accessed February 8, 2026, [https://app.agihouse.org/events/self-evolving-agent-build-day-20251101](https://app.agihouse.org/events/self-evolving-agent-build-day-20251101)  
31. Playwright Agents: AI Plans, Writes & Fixes Your Tests Automatically\! \- YouTube, accessed February 8, 2026, [https://www.youtube.com/watch?v=Ok4QiO1iWMY](https://www.youtube.com/watch?v=Ok4QiO1iWMY)  
32. I built a self-theorizing AI in 4 weeks (Kaleidoscope E8 Cognitive Engine) : r/LocalLLaMA, accessed February 8, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1n2p7uy/i\_built\_a\_selftheorizing\_ai\_in\_4\_weeks/](https://www.reddit.com/r/LocalLLaMA/comments/1n2p7uy/i_built_a_selftheorizing_ai_in_4_weeks/)  
33. How To Allow Your Voice To Record In Clips In Discord \[Guide\] \- YouTube, accessed February 8, 2026, [https://www.youtube.com/watch?v=zeOj49-XkDA](https://www.youtube.com/watch?v=zeOj49-XkDA)  
34. LLM-Powered AI Tutors with Personas for d/Deaf and Hard-of-Hearing Online Learners, accessed February 8, 2026, [https://arxiv.org/html/2411.09873v2](https://arxiv.org/html/2411.09873v2)  
35. Building Intelligent AI Agents. A Deep Dive into Agent-Mem-Tools | by Sulbha Jain \- Medium, accessed February 8, 2026, [https://medium.com/@sulbha.jindal/building-intelligent-ai-agents-9c4aefc9af16](https://medium.com/@sulbha.jindal/building-intelligent-ai-agents-9c4aefc9af16)  
36. Effects of a personalized nutrition program on cardiometabolic health: a randomized controlled trial \- PMC, accessed February 8, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11271409/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11271409/)  
37. A hackable AI assistant using a single SQLite table and a handful of cron jobs | Hacker News, accessed February 8, 2026, [https://news.ycombinator.com/item?id=43681287](https://news.ycombinator.com/item?id=43681287)  
38. Faster Whisper transcription with CTranslate2 \- GitHub, accessed February 8, 2026, [https://github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)  
39. Automatically disconnect a user when he joins a voice channel : r/Discord\_Bots \- Reddit, accessed February 8, 2026, [https://www.reddit.com/r/Discord\_Bots/comments/p768i4/automatically\_disconnect\_a\_user\_when\_he\_joins\_a/](https://www.reddit.com/r/Discord_Bots/comments/p768i4/automatically_disconnect_a_user_when_he_joins_a/)  
40. Part 3 \- Join & Leave Commands | How To Code A Discord.py Music Bot \- YouTube, accessed February 8, 2026, [https://www.youtube.com/watch?v=GEonEC2iKpg](https://www.youtube.com/watch?v=GEonEC2iKpg)  
41. Dive Deep into AI Agent Security: Comprehensive Risk Categorization and Assessment, accessed February 8, 2026, [https://blog.virtueai.com/2025/07/02/dive-deep-into-ai-agent-security-comprehensive-risk-categorization-and-assessment/](https://blog.virtueai.com/2025/07/02/dive-deep-into-ai-agent-security-comprehensive-risk-categorization-and-assessment/)  
42. HumanLayer: Bridging the Gap Between AI Autonomy and Human Control \- Skywork.ai, accessed February 8, 2026, [https://skywork.ai/skypage/en/humanlayer-ai-autonomy-control/1976847500008157184](https://skywork.ai/skypage/en/humanlayer-ai-autonomy-control/1976847500008157184)  
43. The Polymarket API: Architecture, Endpoints, and Use Cases \- Medium, accessed February 8, 2026, [https://medium.com/@gwrx2005/the-polymarket-api-architecture-endpoints-and-use-cases-f1d88fa6c1bf](https://medium.com/@gwrx2005/the-polymarket-api-architecture-endpoints-and-use-cases-f1d88fa6c1bf)  
44. 100+ Best Tech Blogs for Startup Founders & Entrepreneurs in 2026 \- Growth List, accessed February 8, 2026, [https://growthlist.co/tech-blogs/](https://growthlist.co/tech-blogs/)