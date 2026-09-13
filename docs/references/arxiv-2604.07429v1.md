# GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents

Source: https://arxiv.org/html/2604.07429v1#bib.bib21

Retrieved: 2026-09-13 (UTC)

---

\projectpage

<https://gameworld-bench.github.io>
\firstpagefootnoteTechnical Report. ∗Equal contribution. †Corresponding authors.

# GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents

Mingyu Ouyang∗1
  
Siyuan Hu∗1
  
Kevin Qinghong Lin2
  
Hwee Tou Ng1†
  
Mike Zheng Shou1†
Affiliation: 1National University of Singapore, 2University of Oxford

###### Abstract

Towards an embodied generalist for real-world interaction, Multimodal Large Language Model (MLLM) agents still suffer from challenging latency, sparse feedback, and irreversible mistakes.
Video games offer an ideal testbed with rich visual observations and closed-loop interaction, demanding fine-grained perception, long-horizon planning, and precise control.
However, systematically evaluating these capabilities is currently hindered by heterogeneous action interfaces and heuristic verification.
To this end, we introduce GameWorld, a benchmark designed for standardized and verifiable evaluation of MLLMs as generalist game agents in browser environments.
Two game agent interfaces are studied:
(i) *Computer-use agents* that directly emit keyboard and mouse controls, and (ii) *Generalist multimodal agents* that act in a semantic action space via deterministic *Semantic Action Parsing*.
GameWorld contains 34 diverse games and 170 tasks, each paired with *state-verifiable* metrics for *outcome-based* evaluation.
The results across 18 model-interface pairs suggest that even the best performing agent is far from achieving human capabilities on video games.
Extensive experiments of repeated full-benchmark reruns demonstrate the robustness of the benchmark, while further studies on real-time interaction, context-memory sensitivity, and action validity expose more challenges ahead for game agents.
Together, by offering a standardized, verifiable, and reproducible evaluation framework, GameWorld lays a robust foundation for advancing research on multimodal game agents and beyond.

![Refer to caption](https://arxiv.org/html/2604.07429v1/figures/teaser_gameworlds.png)


Figure 1: GameWorld covers 34 diverse games with 170 tasks for standardized evaluation of game agents.

\makeabstract

###### Contents

1. [1 Introduction](https://arxiv.org/html/2604.07429v1#S1 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
2. [2 Game Agent](https://arxiv.org/html/2604.07429v1#S2 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   1. [2.1 Agent Interfaces](https://arxiv.org/html/2604.07429v1#S2.SS1 "In 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   2. [2.2 Computer-Use Agents: Low-Level Controls](https://arxiv.org/html/2604.07429v1#S2.SS2 "In 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   3. [2.3 Generalist Agents: Semantic Action Parsing](https://arxiv.org/html/2604.07429v1#S2.SS3 "In 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   4. [2.4 Agent Harnesses](https://arxiv.org/html/2604.07429v1#S2.SS4 "In 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
3. [3 GameWorld Benchmark](https://arxiv.org/html/2604.07429v1#S3 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   1. [3.1 Benchmark Design](https://arxiv.org/html/2604.07429v1#S3.SS1 "In 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   2. [3.2 Games and Tasks](https://arxiv.org/html/2604.07429v1#S3.SS2 "In 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   3. [3.3 Game Information](https://arxiv.org/html/2604.07429v1#S3.SS3 "In 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   4. [3.4 Browser-Based Sandbox Environment](https://arxiv.org/html/2604.07429v1#S3.SS4 "In 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   5. [3.5 Outcome-Based State-Verifiable Evaluation](https://arxiv.org/html/2604.07429v1#S3.SS5 "In 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
4. [4 Experiments](https://arxiv.org/html/2604.07429v1#S4 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   1. [4.1 Experiment Setup](https://arxiv.org/html/2604.07429v1#S4.SS1 "In 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   2. [4.2 Main Results](https://arxiv.org/html/2604.07429v1#S4.SS2 "In 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   3. [4.3 Benchmark Robustness Under Repeated Evaluation](https://arxiv.org/html/2604.07429v1#S4.SS3 "In 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   4. [4.4 Capability-Aligned Curriculum Analysis](https://arxiv.org/html/2604.07429v1#S4.SS4 "In 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   5. [4.5 Challenges and Analyses:
        
      Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes](https://arxiv.org/html/2604.07429v1#S4.SS5 "In 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
5. [5 Case Study](https://arxiv.org/html/2604.07429v1#S5 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   1. [5.1 Game Agent Interface Comparison: Generalist Agent vs. CUA](https://arxiv.org/html/2604.07429v1#S5.SS1 "In 5 Case Study ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   2. [5.2 Long-Horizon Simulation: Minecraft Resource Collection](https://arxiv.org/html/2604.07429v1#S5.SS2 "In 5 Case Study ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   3. [5.3 Real-Time Reaction and Timing Control: Flappy Bird](https://arxiv.org/html/2604.07429v1#S5.SS3 "In 5 Case Study ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
6. [6 Related Work](https://arxiv.org/html/2604.07429v1#S6 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   1. [6.1 Computer-Use Benchmarks with Online Environments](https://arxiv.org/html/2604.07429v1#S6.SS1 "In 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   2. [6.2 Video Game Benchmarks for LLM and MLLM Agents](https://arxiv.org/html/2604.07429v1#S6.SS2 "In 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   3. [6.3 Game Agents and Scalable Infrastructure](https://arxiv.org/html/2604.07429v1#S6.SS3 "In 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
7. [7 Conclusion](https://arxiv.org/html/2604.07429v1#S7 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
8. [8 Benchmark Runtime](https://arxiv.org/html/2604.07429v1#S8 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   1. [8.1 Preset Configuration](https://arxiv.org/html/2604.07429v1#S8.SS1 "In 8 Benchmark Runtime ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   2. [8.2 Suite Runner](https://arxiv.org/html/2604.07429v1#S8.SS2 "In 8 Benchmark Runtime ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
9. [9 Observation-Action-Evaluation Loop](https://arxiv.org/html/2604.07429v1#S9 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   1. [9.1 Runtime Coordinator](https://arxiv.org/html/2604.07429v1#S9.SS1 "In 9 Observation-Action-Evaluation Loop ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
   2. [9.2 Evaluator and Reset-on-Fail](https://arxiv.org/html/2604.07429v1#S9.SS2 "In 9 Observation-Action-Evaluation Loop ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
10. [10 Browser Sandbox and Game API](https://arxiv.org/html/2604.07429v1#S10 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    1. [10.1 Browser Management](https://arxiv.org/html/2604.07429v1#S10.SS1 "In 10 Browser Sandbox and Game API ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    2. [10.2 Readiness Gate](https://arxiv.org/html/2604.07429v1#S10.SS2 "In 10 Browser Sandbox and Game API ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    3. [10.3 Verifiable State: Game API Schema](https://arxiv.org/html/2604.07429v1#S10.SS3 "In 10 Browser Sandbox and Game API ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
11. [11 Agent Details](https://arxiv.org/html/2604.07429v1#S11 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    1. [11.1 Rolling Memory](https://arxiv.org/html/2604.07429v1#S11.SS1 "In 11 Agent Details ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    2. [11.2 Low-Level Action and Validation](https://arxiv.org/html/2604.07429v1#S11.SS2 "In 11 Agent Details ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    3. [11.3 Semantic Action Parsing](https://arxiv.org/html/2604.07429v1#S11.SS3 "In 11 Agent Details ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
12. [12 Prompt Templates and Game Prompt Blocks](https://arxiv.org/html/2604.07429v1#S12 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    1. [12.1 Prompt Assembly: Shared Templates](https://arxiv.org/html/2604.07429v1#S12.SS1 "In 12 Prompt Templates and Game Prompt Blocks ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    2. [12.2 Per-Game Prompt Library](https://arxiv.org/html/2604.07429v1#S12.SS2 "In 12 Prompt Templates and Game Prompt Blocks ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
    3. [12.3 Model Output-Format Blocks](https://arxiv.org/html/2604.07429v1#S12.SS3 "In 12 Prompt Templates and Game Prompt Blocks ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
13. [13 Costs and Licensing Considerations](https://arxiv.org/html/2604.07429v1#S13 "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")
14. [References](https://arxiv.org/html/2604.07429v1#bib "In GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")

## 1 Introduction

“A game is a series of interesting choices.” — Sid Meier.
Video games tightly couple visual perception, strategic planning, precise timing, and sustained action over long horizons, making them a compelling testbed for evaluating intelligent agents.
Unlike static visual QA or single-turn tool use, games require an agent to repeatedly interpret a changing visual scene, commit to actions with real consequences, and recover from mistakes over many steps.
Within video games, browser games are especially attractive for benchmarking: they are lightweight, mechanically diverse, and easy to reset, providing a scalable alternative to heavyweight game engines or emulators.

Recent Multimodal Large Language Model (MLLM) benchmarks have begun exploring the evaluation of foundation models on games. LMGame-Bench [[33](https://arxiv.org/html/2604.07429v1#bib.bib3)] probes perception, memory, and reasoning through a modular harness across six games. BALROG [[51](https://arxiv.org/html/2604.07429v1#bib.bib15)] emphasizes long-horizon play in classic games with both language and vision tracks. VideoGame-Bench [[79](https://arxiv.org/html/2604.07429v1#bib.bib4)] scales to 23 titles with extended trajectories. Orak [[53](https://arxiv.org/html/2604.07429v1#bib.bib5)] introduces an MCP interface for 12 games. In parallel, execution-based evaluation in interactive environments, as demonstrated by OSWorld [[75](https://arxiv.org/html/2604.07429v1#bib.bib10)] for computer-use tasks, has shown that real interaction reveals performance gaps that static datasets hide. These efforts collectively improve the realism and scale of game-based evaluation, yet several systematic challenges remain unaddressed. Current evaluation is still hindered by heterogeneous action interfaces, latency coupling in real-time interaction, and the lack of outcome-based or verifiable evaluation. Many existing benchmarks still rely on heuristic, OCR, or VLM-as-judge methods, making results harder to verify, reproduce, and diagnose.

To bridge this gap, we introduce GameWorld, a standardized benchmark for multimodal game agents in browser environments. GameWorld comprises 34 browser games spanning five genres (Runner, Arcade, Platformer, Puzzle, and Simulation) with 170 diverse tasks. A browser-based sandbox pauses game execution during model inference, decoupling inference latency from gameplay so that scores reflect decision quality rather than response speed.
Each task is paired with an outcome-based state-verifiable evaluator over serialized gameAPI state, producing deterministic progress and success signals without perceptual noise.
Under this shared runtime, we study two agent interfaces: *Computer-Use Agents* (CUAs), which emit raw keyboard and mouse controls, and *Generalist Multimodal Agents*, which act through deterministic *Semantic Action Parsing*. Together, we evaluate 18 model–interface pairs of game agents.

Beyond the main leaderboard, we conduct a set of analyses to study robustness of our benchmark and interface-wise behavior. Repeated full-benchmark reruns show that GameWorld yields stable aggregate measurements with only limited run-to-run variation, supporting its use as a reproducible evaluation platform rather than a one-off leaderboard snapshot. We further establish GameWorld-RT, an unpaused real-time benchmark variant in which environment dynamics continue during inference, making response latency part of the task itself.
Combining main results with complementary analyses on context-memory sensitivity and action validity, we reveal four broader findings: (i) Current game agents can often make meaningful partial progress but remain far from reliable task completion and human-level performance. (ii) Capability-aligned curriculum profiles show that game-agent performance largely inherits the strengths of the underlying foundation models, with comparatively stronger results on reactive-control and symbolic-reasoning games but clear weaknesses on basic timing grounding, spatial navigation, and long-horizon coordination tasks. (iii) Real-time interaction is a distinct challenge since reasoning speed, correctness, and action timing are more tightly coupled. (iv) The two agent interfaces exhibit similar capability bottleneck and distinct trade-offs in context-memory rounds and instruction-following reliability.
Together, these analyses expose strengths and limitations of current game agents and help guide future improvement directions.

Our contributions are as follows:

* •

  A standardized and comprehensive benchmark for multimodal game agents.
  GameWorld provides 34 browser games spanning 5 genres and 170 tasks. It supports both *Computer-Use Agents* and *Generalist Multimodal Agents* under a shared executable action space via deterministic *Semantic Action Parsing*, together with a sandbox that decouples inference latency from gameplay, enabling standardized evaluation across different control interfaces.
* •

  A universal outcome-based state-verifiable evaluator.
  Unlike prior game benchmarks that rely on noisy visual heuristics or VLM-as-judge pipelines, GameWorld evaluates entirely through outcome-based metrics computed from serialized gameAPI state. We compute deterministic task success and normalized progress directly from task-relevant game variables, ensuring noise-free and fully reproducible evaluation.
* •

  A suite of interface-aware benchmark analyses.
  GameWorld contributes repeated-evaluation robustness studies to characterize the reproducibility of the benchmark itself. It further provides capability-aligned curriculum analyses, the real-time benchmark variant GameWorld-RT, context-memory sensitivity analysis, and action-validity diagnostics to study latency coupling, capability bottlenecks, context-memory trade-offs, and instruction-following reliability across both game-agent interfaces.

![Refer to caption](https://arxiv.org/html/2604.07429v1/overview.png)


Figure 2: 
Overview of the GameWorld benchmark with four modules:
(i) MLLMs as game agents,
(ii) Browser-based sandbox environment,
(iii) Games & tasks library,
and (iv) Outcome-based state-verifiable evaluation. This closes a continuous and interactive observation-action-verification loop for systematically evaluating game agents.

## 2 Game Agent

|  |  |
| --- | --- |
| Game Agent Interfaces | |
| Computer-Use Agent | Generalist Multimodal Agent |
| Action Space: Computer-use function calls   Native tools of mouse and keyboard events.    - mouse\_move(x,y)      # move pointer    - left\_click(x,y)      # primary click    - right\_click(x,y)      # secondary click    - double\_click(x,y)      # double click    - click\_hold(x,y)      # triple click    - drag((x1,y1),(x2,y2))      # drag pointer    - scroll\_up(n)      # scroll up    - scroll\_down(n)      # scroll down    - type(text)      # text entry    - press\_key(key)      # single key    - press\_keys(key1,key2)      # key combo    - wait(duration)      # idle | Action Space: Game-specific function calls   Semantic functions parsed into low-level controls.    - move\_forward()    # player: forward    - move\_backward()    # player: backward    - move\_left()    # player: strafe left    - move\_right()    # player: strafe right    - look\_up()    # view: camera up    - look\_down()    # view: camera down    - look\_left()    # view: camera turn left    - look\_right()    # view: camera turn right    - action\_jump()    # action: player jump    - action\_duck()    # action: player duck    - weapon\_fire()    # item: fire weapon    - no\_op()    # idle: no operation |
| Unified Control Space (Atomic Events) | |
| Mouse: mouse\_move(x,y)   mouse\_down(button)   mouse\_up(button)   scroll(amount)  Keyboard: key\_down(key)   key\_up(key)  Others: wait(duration)   idle() | |

Table 1: 
Two game agent interfaces and action-space taxonomy. Both interfaces are normalized to a unified control space of atomic human-computer interaction events.

A central challenge in benchmarking MLLMs as game agents is that models generate the actions in multiple forms to interact with the games. Even for the same operation, tool-call functions can be vary: a screen click becomes left\_click(x,y) in one API and computer(action="click",coordinate=[x,y]) in another. Models also differ in abstraction because of the agent implementation, with some emitting raw keyboard and mouse controls while others reason in terms of high-level game actions. To standardize evaluation across these heterogeneous interfaces, we define two agent interfaces, Computer-Use and Generalist (Figure [2](https://arxiv.org/html/2604.07429v1#S1.F2 "Figure 2 ‣ 1 Introduction ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"), Module i), and normalize all outputs into a shared executable action space defined over atomic human-computer interaction events.

### 2.1 Agent Interfaces

At each step, the agent observes a screenshot of the current game state, produces an action through the model, and the environment executes it. A verifiable evaluator then checks the resulting state against the task objective. The agent’s raw output is normalized into a shared set of executable atomic events: mouse\_move, mouse\_down, mouse\_up, key\_down, key\_up, scroll, and wait. These events define the executor-level unified control space. Each game role exposes only the subset needed for that environment while preserving a common runtime contract across models.

As shown in Table [1](https://arxiv.org/html/2604.07429v1#S2.T1 "Table 1 ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"), we distinguish two game-agent interfaces: (i) Computer-Use Agents that directly emit low-level keyboard and mouse controls (Section [2.2](https://arxiv.org/html/2604.07429v1#S2.SS2 "2.2 Computer-Use Agents: Low-Level Controls ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")), and (ii) Generalist Multimodal Agents that act in a semantic space and are executed through deterministic *Semantic Action Parsing* (Section [2.3](https://arxiv.org/html/2604.07429v1#S2.SS3 "2.3 Generalist Agents: Semantic Action Parsing ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")).
To comprehensively assess the current landscape of game agents, we evaluate both state-of-the-art proprietary models and open-source models. Models with native computer-use capabilities are evaluated under both CUA and Generalist interfaces. This shared protocol also enables interface-aware analyses of benchmark robustness, real-time interaction, context-memory sensitivity, and action validity under one common runtime and verifier.

### 2.2 Computer-Use Agents: Low-Level Controls

Computer-Use Agents (CUAs) directly emit low-level keyboard and mouse interactions such as mouse\_move(x,y), left\_click(x,y), and press\_key(key), bearing full responsibility for both strategic decision-making and precise action grounding. These commands are executed under the same unified runtime contract and grounded into the shared executor-level event space. Since CUAs must output exact coordinates and key sequences from visual observations, this interface most closely mirrors how a human player interacts with the game, and is therefore highly sensitive to inference latency in real-time settings.

We enforce a *one-action-per-step* constraint for evaluation consistency over CUAs: each model response must contain exactly one executable action that satisfies the role-specific keyboard or mouse control specification. Note that key combinations are allowed. Actions that fall outside the game’s permitted control interface (e.g., OS-level APIs) are rejected, ensuring that CUA scores reflect in-game capabilities under a fixed action budget.

### 2.3 Generalist Agents: Semantic Action Parsing

Generalist Multimodal Agents excel at semantic planning but typically lack the ability to produce precise pixel coordinates or fine-grained key-timing sequences required for direct game control. To place them under the same benchmark runtime and verifier as CUAs, we introduce *Semantic Action Parsing*: for each game and role, a deterministic parser maps every semantic action to a fixed low-level interaction command under the same unified runtime contract. Because this mapping is deterministic, it removes parser-side stochasticity and supports more interpretable interface-conditioned comparisons under the same executor-level physical event space.
We further enforce *Action Atomicity* at the model-step level: each model response must specify one interaction command per step. What is disallowed is any multi-command macro that bundles several semantically distinct decisions into one step.

### 2.4 Agent Harnesses

Foundation models alone are insufficient for sustained gameplay: the agent needs structured prompts, short and long-term memory, and model-specific tool interfaces to act coherently over long horizons [[33](https://arxiv.org/html/2604.07429v1#bib.bib3), [78](https://arxiv.org/html/2604.07429v1#bib.bib41), [56](https://arxiv.org/html/2604.07429v1#bib.bib42)]. Therefore, we wrap each model in a shared agent harness that standardizes these components across all models.
Appendix [11](https://arxiv.org/html/2604.07429v1#S11 "11 Agent Details ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") further details the harness components used in our implementation.

#### 2.4.1 Structured Prompt

To reduce prompt-induced variance across models and games, we define a fixed prompt template with four components: #Game Rules, #Role and Controls, #Task Instruction, and #Output Format. The template structure stays constant across all experiments; only the game-specific rules, role description, and task objective are swapped per configuration, keeping cross-model comparisons controlled.
The exact shared templates, per-game prompt blocks, and model-specific output-format blocks are listed in Appendices [12.1](https://arxiv.org/html/2604.07429v1#S12.SS1 "12.1 Prompt Assembly: Shared Templates ‣ 12 Prompt Templates and Game Prompt Blocks ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"), [12.2](https://arxiv.org/html/2604.07429v1#S12.SS2 "12.2 Per-Game Prompt Library ‣ 12 Prompt Templates and Game Prompt Blocks ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"), and [12.3](https://arxiv.org/html/2604.07429v1#S12.SS3 "12.3 Model Output-Format Blocks ‣ 12 Prompt Templates and Game Prompt Blocks ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").

#### 2.4.2 Context Memory

The agent maintains a rolling memory module that stores the most recent rounds of interaction. Each round records the sequence user\_prompt →\rightarrow screenshot →\rightarrow reasoning →\rightarrow action, and recent rounds are prepended as an Action History block before the current observation. This gives the agent short-horizon trajectory context, allowing it to avoid repeating failed actions and to maintain consistency across consecutive steps. Our experiments on the effect of context memory on the performance of game agents are in Section [4.5.2](https://arxiv.org/html/2604.07429v1#S4.SS5.SSS2 "4.5.2 Context-Memory Sensitivity ‣ 4.5 Challenges and Analyses:Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").

#### 2.4.3 Reasoning

Reasoning is becoming increasingly important for agent capabilities, especially on long-horizon tasks where the agent must maintain subgoals rather than react frame by frame. This is also particularly relevant for visual reasoning: more deliberate inspection of visual inputs helps MLLMs parse visual information more reliably. Tool-assisted operations such as image zooming or cropping can further improve environment understanding with close observations. In video games, such text or visual reasoning is often necessary to support accurate perception and decision making. However, the longer reasoning time also introduces additional latency, which can be detrimental to the performance of game agents (See Section [4.5.1](https://arxiv.org/html/2604.07429v1#S4.SS5.SSS1 "4.5.1 GameWorld-RT: Real-Time Benchmark ‣ 4.5 Challenges and Analyses:Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")).

#### 2.4.4 Customized Function Calling

We register the game’s semantic actions and computer-use primitives as callable tools for each model, using each model provider’s native function-calling (also known as tool-calling) interface (e.g., OpenAI function calling, Claude tool use, Gemini function declarations). This preserves each model’s native agentic capability within its own API contract for the best performance, while keeping the harness-level protocol uniform across all models.
Appendices [11.2](https://arxiv.org/html/2604.07429v1#S11.SS2 "11.2 Low-Level Action and Validation ‣ 11 Agent Details ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") and [11.3](https://arxiv.org/html/2604.07429v1#S11.SS3 "11.3 Semantic Action Parsing ‣ 11 Agent Details ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") provide the exact legality checks and deterministic action-resolution rules used by the runtime.

Table 2: 
Comparison with representative game or computer-use agent benchmarks.
#Tasks denotes the number of *specific instructions, goals, or questions*.

|  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Benchmark | #  Games | #  Tasks | #  Models | Vision-  Centric | Config.  Init. State | Task-  Oriented | Parallel  Inst. | Verif.  Eval. | Notes |
| Static Benchmarks | | | | | | | | | |
| GameQA [[68](https://arxiv.org/html/2604.07429v1#bib.bib12)] | 30 | 158 | 8 | ✗ | NA | ✗ | NA | ✗ | Code2Logic QA. |
| VideoGameQA [[62](https://arxiv.org/html/2604.07429v1#bib.bib16)] | 800+ | 9 | 16 | ✓ | NA | ✗ | NA | ✗ | Non-interactive QA dataset. |
| Interactive Benchmarks | | | | | | | | | |
| MCU [[84](https://arxiv.org/html/2604.07429v1#bib.bib17)] | 1 | 150 | 4 | ✓ | ✓ | ✓ | ✗ | ✗ | Minecraft only. |
| LMGame-Bench [[33](https://arxiv.org/html/2604.07429v1#bib.bib3)] | 6 | 6 | 13 | ✗ | ✗ | ✓ | ✗ | ✓ | Text-centric benchmark. |
| VideoGame-Bench [[79](https://arxiv.org/html/2604.07429v1#bib.bib4)] | 23 | 23 | 5 | ✓ | ✗ | ✓ | ✗ | ✗ | Heuristics evaluation. |
| FlashAdventure [[3](https://arxiv.org/html/2604.07429v1#bib.bib1)] | 34 | 34 | 7 | ✓ | ✗ | ✓ | ✗ | ✓ | Flash-based stories; CUA-as-a-Judge. |
| V-MAGE [[83](https://arxiv.org/html/2604.07429v1#bib.bib19)] | 5 | 30 | 7 | ✓ | ✓ | ✓ | ✗ | ✗ | 5 games only. |
| BALROG [[51](https://arxiv.org/html/2604.07429v1#bib.bib15)] | 6 | 48 | 12 | ✗ | ✗ | ✓ | ✓ | ✓ | Visual input degrades performance. |
| NitroGen [[43](https://arxiv.org/html/2604.07429v1#bib.bib7)] | 10 | 30 | 1 | ✓ | ✗ | ✗ | ✗ | ✓ | No language-conditioned tasks. |
| Orak [[53](https://arxiv.org/html/2604.07429v1#bib.bib5)] | 12 | 12 | 15 | ✗ | ✗ | ✓ | ✗ | ✓ | States pre-processed into text. |
| GameVerse [[80](https://arxiv.org/html/2604.07429v1#bib.bib18)] | 15 | 15 | 7 | ✓ | ✗ | ✓ | ✗ | ✗ | Semantic + GUI control. |
| GameWorld | 34 | 170 | 18 | ✓ | ✓ | ✓ | ✓ | ✓ | Scalable tasks, state-verifiable evaluation. |

## 3 GameWorld Benchmark

Table 3: 
Game genre of the GameWorld benchmark. Each row includes one representative screenshot, the dominant interaction mechanics, and the game IDs used in our evaluation.

|  |  |  |  |
| --- | --- | --- | --- |
| Game Genre | Example Screenshot | Key Mechanics | Games |
| Arcade  (7) | [Uncaptioned image] Source: pac-man | Fast-paced, closed-loop  control with dynamic  multi-entity tracking,  reactive evasion, and reward  collection. | 5-breakout  8-core-ball  15-google-snake  23-pacman  25-rocket-league-2d  33-worlds-hardest-game  34-worlds-hardest-game-2 |
| Platformer  (8) | [Uncaptioned image] Source: captaincallisto | Spatiotemporal navigation  demanding precise  physics-based movement,  localized planning, and  hazard evasion across  structured terrains. | 2-another-gentlemans-adventure  6-captaincallisto  10-doodle-jump  14-geodash  17-mario-game  22-ovo  24-restless-wing-syndrome  30-vex-3 |
| Puzzle  (7) | [Uncaptioned image] Source: astray | Discrete state-space  exploration focusing  on long-horizon strategic  planning and logical  decision-making. | 1-2048  3-astray  16-hextris  19-minesweeper  27-stack  29-tetris  32-wordle |
| Runner  (8) | [Uncaptioned image] Source: temple-run-2 | Continuous state progression  requiring high-frequency  reactive control and precise  timing for obstacle avoidance. | 4-boxel-rebound  7-chrome-dino  9-cubefield  11-edge-surf  13-flappy-bird  21-ns-shaft  26-run-3  28-temple-run-2 |
| Simulation  (4) | [Uncaptioned image] Source: monkey-mart | Open-ended, multi-objective  environments evaluating  resource management,  multi-character cooperation,  or strategic exploration. | 12-fireboy-and-watergirl  18-minecraft-clone-glm  20-monkey-mart  31-wolf3d |

### 3.1 Benchmark Design

Evaluating agents in games introduces challenges that existing game agent benchmarks have not fully addressed. Most cover few games within narrow genres, limiting the diversity and scale needed for comprehensive evaluation. In real-time games, agent inference latency directly affects outcomes: a two-second pause can mean the character has already fallen off the platform. Moreover, most existing benchmarks rely on heuristic, OCR or VLM-as-judge methods for evaluation, introducing noise that makes results difficult to verify.

GameWorld addresses each of these with: (i) a curated benchmark spanning five genres, with standardized task definitions including: task instruction, configurable initialization state, target metric, and evaluation configurations; (ii) a sandbox environment that manages game execution and decouples runtime latency from agent evaluation (Section [3.4](https://arxiv.org/html/2604.07429v1#S3.SS4 "3.4 Browser-Based Sandbox Environment ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")); and (iii) a state-verifiable evaluator that provides outcome-based metrics from serialized gameAPI state (Section [3.5](https://arxiv.org/html/2604.07429v1#S3.SS5 "3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents")).
Table [2](https://arxiv.org/html/2604.07429v1#S2.T2 "Table 2 ‣ 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") compares GameWorld with representative prior computer-use or video game benchmarks.
Additional implementation details on preset composition, suite expansion, and runtime coordination are provided in Appendices [8](https://arxiv.org/html/2604.07429v1#S8 "8 Benchmark Runtime ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") and [9](https://arxiv.org/html/2604.07429v1#S9 "9 Observation-Action-Evaluation Loop ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").

### 3.2 Games and Tasks

As shown in Table [3](https://arxiv.org/html/2604.07429v1#S3.T3 "Table 3 ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"), GameWorld comprises 34 browser-based games and 170 task instructions spanning five genres: Runner, Arcade, Platformer, Puzzle, and Simulation. The genres are selected to cover distinct capabilities that game agents must exhibit. Runner and Arcade games demand high-frequency reactive control and multi-entity tracking under continuous time pressure. Platformers require precise, physics-aware spatial navigation. Puzzles test logical reasoning and long-horizon planning in discrete state spaces. Simulations present open-ended, multi-objective environments involving resource management or 3D spatial reasoning.

Each task pairs a natural-language instruction with a quantitative target and a verifiable evaluator. Instructions are goal-oriented but open-ended in execution: the agent receives no intermediate guidance and must autonomously decide actions from visual observations within a fixed step budget. We define two complementary metrics: Success Rate (𝒮​ℛ∈{0,1}\mathcal{SR}\in\{0,1\}), the fraction of runs meeting the target, and Progress (𝒫​𝒢∈[0,1]\mathcal{PG}\in[0,1]), a normalized measure of how far the agent advanced toward the objective, providing partial credit for incomplete runs.

### 3.3 Game Information

Table [4](https://arxiv.org/html/2604.07429v1#S3.T4 "Table 4 ‣ 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") lists the 34 games used in the GameWorld benchmark.
Beyond the genre-level taxonomy in Table [3](https://arxiv.org/html/2604.07429v1#S3.T3 "Table 3 ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"), this inventory provides a game-by-game view with IDs, source citations, short mechanic summaries, and representative screenshots. The collection are designed spanning a wide range of interaction structures, from sparse board-state reasoning in games such as 2048 and Minesweeper, to continuous real-time control in Temple Run 2 and Pac-Man, as well as open-ended simulation in Monkey Mart and Minecraft Clone. This diversity is reflected not only in task mechanics but also in visual presentation, including 2D and 3D viewpoints, diverse HUDs, minimal puzzle layouts, and character-centric platforming scenes, which together motivate a unified benchmark interface across all games.

Table 4: Game inventory for the 34-game GameWorld benchmark.

|  |  |  |  |
| --- | --- | --- | --- |
| ID | Game | Description | Gameplay Screenshot |
| 1-2048 | 2048 [[13](https://arxiv.org/html/2604.07429v1#bib.bib53)] | Sliding-tile puzzle where the player merges matching tiles to build larger values under limited board space. | [Uncaptioned image] |
| 2-another-gentlemans-adventure | Another   Gentleman’s   Adventure [[15](https://arxiv.org/html/2604.07429v1#bib.bib54)] | Platform adventure centered on movement, jumping, coin collection, and enemy avoidance. | [Uncaptioned image] |
| 3-astray | Astray [[66](https://arxiv.org/html/2604.07429v1#bib.bib55)] | Maze-navigation puzzle in which the player must steer through a labyrinth to find the exit. | [Uncaptioned image] |
| 4-boxel-rebound | Boxel Rebound [[19](https://arxiv.org/html/2604.07429v1#bib.bib56)] | Precision auto-runner where the player times jumps to survive hazards and reach the end of each level. | [Uncaptioned image] |
| 5-breakout | Breakout [[6](https://arxiv.org/html/2604.07429v1#bib.bib57)] | Classic brick-breaking arcade game where the player controls a paddle to keep the ball in play and clear bricks. | [Uncaptioned image] |
| 6-captaincallisto | Captain Callisto [[22](https://arxiv.org/html/2604.07429v1#bib.bib58)] | Platform adventure with traversal, jumping, and jetpack-assisted movement toward the exit. | [Uncaptioned image] |
| 7-chrome-dino | Chrome Dino [[27](https://arxiv.org/html/2604.07429v1#bib.bib59)] | Endless runner in which the dinosaur must jump over obstacles and stay alive as speed increases. | [Uncaptioned image] |
| 8-core-ball | Core Ball [[55](https://arxiv.org/html/2604.07429v1#bib.bib60)] | Timing-based arcade game where numbered balls must be fired into a rotating core without collisions. | [Uncaptioned image] |
| 9-cubefield | Cubefield [[1](https://arxiv.org/html/2604.07429v1#bib.bib61)] | Endless 3D runner where the player steers through dense cube fields and survives as long as possible. | [Uncaptioned image] |
| 10-doodle-jump | Doodle Jump [[54](https://arxiv.org/html/2604.07429v1#bib.bib62)] | Vertical platformer where the player chains landings to keep climbing through increasingly complex layouts. | [Uncaptioned image] |
| 11-edge-surf | Edge Surf [[45](https://arxiv.org/html/2604.07429v1#bib.bib63)] | Surfing endless runner focused on obstacle avoidance, item collection, and survival over long distances. | [Uncaptioned image] |
| 12-fireboy-and-watergirl | Fireboy and   Watergirl [[4](https://arxiv.org/html/2604.07429v1#bib.bib64)] | Cooperative puzzle-platformer where two characters with asymmetric constraints must coordinate to finish a level. | [Uncaptioned image] |




Table [4](https://arxiv.org/html/2604.07429v1#S3.T4 "Table 4 ‣ 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") (continued): Game inventory for the 34-game GameWorld benchmark.

|  |  |  |  |
| --- | --- | --- | --- |
| ID | Game | Description | Gameplay Screenshot |
| 13-flappy-bird | Flappy Bird [[48](https://arxiv.org/html/2604.07429v1#bib.bib65)] | One-button flying game that tests precise timing while weaving through pipes. | [Uncaptioned image] |
| 14-geodash | GeoDash [[35](https://arxiv.org/html/2604.07429v1#bib.bib66)] | Geometry-Dash-style auto-runner where success depends on tightly timed jumps over spikes and gaps. | [Uncaptioned image] |
| 15-google-snake | Google Snake [[28](https://arxiv.org/html/2604.07429v1#bib.bib67)] | Classic Snake variant where the agent grows by eating food while avoiding walls and self-collisions. | [Uncaptioned image] |
| 16-hextris | Hextris [[31](https://arxiv.org/html/2604.07429v1#bib.bib68)] | Hexagon-based matching puzzle where the agent rotates and places colored blocks to prevent overflow. | [Uncaptioned image] |
| 17-mario-game | Mario Game [[24](https://arxiv.org/html/2604.07429v1#bib.bib69)] | Super-Mario-style platformer with enemy avoidance, jumping, and long-horizon navigation to the flagpole. | [Uncaptioned image] |
| 18-minecraft-clone-glm | Minecraft Clone [[85](https://arxiv.org/html/2604.07429v1#bib.bib70)] | First-person sandbox game focused on movement, camera control, resource gathering, and direct world interaction. | [Uncaptioned image] |
| 19-minesweeper | Minesweeper [[46](https://arxiv.org/html/2604.07429v1#bib.bib71)] | Logic puzzle that requires deducing mine locations from local numeric clues without triggering a mine. | [Uncaptioned image] |
| 20-monkey-mart | Monkey Mart [[67](https://arxiv.org/html/2604.07429v1#bib.bib72)] | Store-management simulation where the player harvests goods, stocks shelves, and serves customers efficiently. | [Uncaptioned image] |
| 21-ns-shaft | NS-Shaft [[47](https://arxiv.org/html/2604.07429v1#bib.bib73)] | Falling-platform runner in which the player descends through shifting platforms while avoiding hazards. | [Uncaptioned image] |
| 22-ovo | OvO [[20](https://arxiv.org/html/2604.07429v1#bib.bib74)] | Fast platformer with traps, wall interactions, and jump timing for level-by-level navigation. | [Uncaptioned image] |
| 23-pacman | Pac-Man [[37](https://arxiv.org/html/2604.07429v1#bib.bib75)] | Maze-chase arcade game focused on pellet collection, ghost avoidance, and opportunistic ghost hunting. | [Uncaptioned image] |
| 24-restless-wing-syndrome | Restless Wing   Syndrome [[40](https://arxiv.org/html/2604.07429v1#bib.bib76)] | Platformer with periodic automatic flapping, requiring the player to work with a constrained movement rhythm. | [Uncaptioned image] |




Table [4](https://arxiv.org/html/2604.07429v1#S3.T4 "Table 4 ‣ 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") (continued): Game inventory for the 34-game GameWorld benchmark.

|  |  |  |  |
| --- | --- | --- | --- |
| ID | Game | Description | Gameplay Screenshot |
| 25-rocket-league-2d | Rocket League 2D [[44](https://arxiv.org/html/2604.07429v1#bib.bib77)] | Side-view car-soccer game requiring positioning, jumping, and ball control to score goals. | [Uncaptioned image] |
| 26-run-3 | Run 3 [[14](https://arxiv.org/html/2604.07429v1#bib.bib78)] | Tunnel runner that combines lateral movement and jumps to cross gaps in a rotating corridor. | [Uncaptioned image] |
| 27-stack | Stack [[39](https://arxiv.org/html/2604.07429v1#bib.bib79)] | Timing puzzle in which moving blocks must be dropped with precise alignment to keep the tower stable. | [Uncaptioned image] |
| 28-temple-run-2 | Temple Run 2 [[36](https://arxiv.org/html/2604.07429v1#bib.bib80)] | Endless runner requiring turn, jump, and slide decisions under high-speed reactive pressure. | [Uncaptioned image] |
| 29-tetris | Tetris [[52](https://arxiv.org/html/2604.07429v1#bib.bib81)] | Falling-block puzzle focused on line clearing, spatial planning, and managing long-term board structure. | [Uncaptioned image] |
| 30-vex-3 | Vex 3 [[2](https://arxiv.org/html/2604.07429v1#bib.bib82)] | Precision platformer built around checkpoints, trap avoidance, and accurate movement through hazard-heavy levels. | [Uncaptioned image] |
| 31-wolf3d | Wolfenstein 3D [[58](https://arxiv.org/html/2604.07429v1#bib.bib83)] | First-person shooter benchmark emphasizing navigation, target detection, and combat survival in a 3D maze. | [Uncaptioned image] |
| 32-wordle | Wordle [[73](https://arxiv.org/html/2604.07429v1#bib.bib84)] | Word-guessing puzzle where the player uses color feedback to infer a hidden five-letter word. | [Uncaptioned image] |
| 33-worlds-hardest-game | World’s Hardest Game [[17](https://arxiv.org/html/2604.07429v1#bib.bib85)] | Precision dodge maze where the player collects coins and reaches the exit while avoiding moving enemies. | [Uncaptioned image] |
| 34-worlds-hardest-game-2 | World’s Hardest Game 2 [[18](https://arxiv.org/html/2604.07429v1#bib.bib86)] | A harder follow-up dodge maze with denser enemy patterns and stricter movement precision. | [Uncaptioned image] |

### 3.4 Browser-Based Sandbox Environment

The central design goal of the sandbox is to decouple agent decision quality from inference speed. In real-time games, a slower model faces a harder game state by the time it acts, conflating thinking time with gameplay ability. To eliminate this confound, the sandbox can pause game execution during model inference, so every agent faces identical game dynamics regardless of response latency. Scores then reflect what the agent decides, not how fast it responds. The sandbox also supports real-time evaluation for studying how latency affects gameplay in practice.

The sandbox ensures each game runs in an isolated browser instance following a strict observation-action loop: capture a screenshot, query the model, execute one action. Before the first agent decision and after each reset, the environment waits until the game reports an actionable state (by default, ready or playing) and absorbs transient loading or menu phases through this readiness gate. Besides this, the sandbox also supports configurable game speed and deterministic seed settings for evaluation reproducibility.
Appendix [10](https://arxiv.org/html/2604.07429v1#S10 "10 Browser Sandbox and Game API ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") details the browser manager, readiness gate, and Game API contract behind this sandbox.

### 3.5 Outcome-Based State-Verifiable Evaluation

One key characteristic of GameWorld is that evaluation is based on interaction *outcomes* rather than on the model response itself, with the underlying game state remains *verifiable* throughout agent execution. Most existing game benchmarks evaluate agents through OCR, pixel-level heuristics, or VLM-as-judge pipelines, all of which may introduce noise into the evaluation. GameWorld instead adopts outcome-based state-verifiable evaluation: for each game, we inject a structured JavaScript bridge that exposes serialized gameAPI state directly to the evaluator, including lifecycle status, terminal metadata, and task-relevant gameplay variables such as score, level, coordinates, lives, coins, or checkpoints. This yields deterministic, fully verifiable signals with no perceptual noise. In total, we instrument 233 task-relevant state fields across 34 games (averaging available 6.85 fields per game), with each field is manually designed to capture a gameplay quantity relevant to task evaluation.
Appendices [9](https://arxiv.org/html/2604.07429v1#S9 "9 Observation-Action-Evaluation Loop ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") and [10.3](https://arxiv.org/html/2604.07429v1#S10.SS3 "10.3 Verifiable State: Game API Schema ‣ 10 Browser Sandbox and Game API ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") further show the details of the observation-action-evaluation loop and provide a concrete example of the serialized gameAPI verifiable-state schema.

At every step, the evaluator reads the current gameAPI state, resolves a task score from either a configured scalar field or an aggregate over multiple fields, and computes the two metrics defined in Section [3](https://arxiv.org/html/2604.07429v1#S3 "3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"): 𝒮​ℛ\mathcal{SR} (whether the task succeeds) and 𝒫​𝒢\mathcal{PG} (normalized task progress from the configured start score to the target score). This task-level 𝒫​𝒢\mathcal{PG} is distinct from any native in-game game\_state.progress, which we keep only as diagnostic game progress. Stopping and status are then determined by target reach, terminal signals, task-specific end-field rules, and the fixed step budget. When an agent hits a terminal failure (e.g., losing all lives), the environment resets and the agent continues under the same step budget rather than being immediately terminated, while preserving the run-level best progress reached so far. This prevents a single early mistake from zeroing out an otherwise competent run.

|  |  |  |  |
| --- | --- | --- | --- |
| Model | Computer-Use  Agent | Generalist  Agent | Model Description |
| Proprietary | | | |
| [Uncaptioned image] Claude-Sonnet-4.6 [[5](https://arxiv.org/html/2604.07429v1#bib.bib25)] | ✓ | ✓ | Anthropic multimodal model supporting computer-use. |
| [Uncaptioned image] Gemini-2.5-Computer-Use [[29](https://arxiv.org/html/2604.07429v1#bib.bib27)] | ✓ |  | Computer-use model built on Gemini 2.5 Pro. |
| [Uncaptioned image] Gemini-3-Flash-Preview [[26](https://arxiv.org/html/2604.07429v1#bib.bib26)] |  | ✓ | Google fast multimodal foundation model. |
| [Uncaptioned image] GLM-4.6V [[32](https://arxiv.org/html/2604.07429v1#bib.bib28)] |  | ✓ | Z.ai VLM with tool use. |
| [Uncaptioned image] GPT-5.2 [[50](https://arxiv.org/html/2604.07429v1#bib.bib22)] |  | ✓ | OpenAI multimodal function model with reasoning. |
| [Uncaptioned image] Grok-4.1-Fast-Reasoning [[74](https://arxiv.org/html/2604.07429v1#bib.bib24)] |  | ✓ | xAI foundation model with fast reasoning. |
| [Uncaptioned image] Kimi-K2.5 [[65](https://arxiv.org/html/2604.07429v1#bib.bib23)] |  | ✓ | Moonshot multimodal foundation model. |
| [Uncaptioned image] OpenAI-Computer-Use [[49](https://arxiv.org/html/2604.07429v1#bib.bib31)] | ✓ |  | OpenAI native computer-use agent. |
| [Uncaptioned image] Qwen3-VL-Plus [[8](https://arxiv.org/html/2604.07429v1#bib.bib21)] | ✓ | ✓ | Alibaba hosted visual foundation model. |
| [Uncaptioned image] Seed-1.8 [[30](https://arxiv.org/html/2604.07429v1#bib.bib29)] | ✓ | ✓ | ByteDance Seed’s multimodal model. |
| Open-Source | | | |
| [Uncaptioned image] Qwen3-VL-235B-A22B [[8](https://arxiv.org/html/2604.07429v1#bib.bib21)] | ✓ | ✓ | Open flagship Qwen3-VL Mixture-of-Experts model. |
| [Uncaptioned image] Qwen3-VL-30B-A3B [[8](https://arxiv.org/html/2604.07429v1#bib.bib21)] | ✓ | ✓ | Open compact Qwen3-VL Mixture-of-Experts model. |
| [Uncaptioned image] UI-TARS-1.5-7B [[57](https://arxiv.org/html/2604.07429v1#bib.bib30)] | ✓ |  | Open-weight native GUI agent by ByteDance Seed. |

Table 5: 
Model profiles in GameWorld. Each model is evaluated as a Computer-Use Agent, a Generalist multimodal agent, or both.

## 4 Experiments

### 4.1 Experiment Setup

We evaluate 13 base models in the GameWorld benchmark across both Computer-Use Agent (CUA) and Generalist Agent interfaces. In total, this yields 18 model–agent-interface pairs (8 CUAs + 10 Generalist Agents), summarized in the model taxonomy table in Table [5](https://arxiv.org/html/2604.07429v1#S3.T5 "Table 5 ‣ 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"). The evaluated models include:

* •

  Proprietary models: Claude-Sonnet-4.6 [[5](https://arxiv.org/html/2604.07429v1#bib.bib25)], Gemini-2.5-Computer-Use [[29](https://arxiv.org/html/2604.07429v1#bib.bib27)], Gemini-3-Flash-Preview [[26](https://arxiv.org/html/2604.07429v1#bib.bib26)], GLM-4.6V [[32](https://arxiv.org/html/2604.07429v1#bib.bib28)], GPT-5.2 [[50](https://arxiv.org/html/2604.07429v1#bib.bib22)], Grok-4.1-Fast-Reasoning [[74](https://arxiv.org/html/2604.07429v1#bib.bib24)], Kimi-K2.5 [[65](https://arxiv.org/html/2604.07429v1#bib.bib23)], OpenAI-Computer-Use [[49](https://arxiv.org/html/2604.07429v1#bib.bib31)], Qwen3-VL-Plus [[8](https://arxiv.org/html/2604.07429v1#bib.bib21)], and Seed-1.8 [[30](https://arxiv.org/html/2604.07429v1#bib.bib29)].
* •

  Open-source models: Qwen3-VL-235B-A22B [[8](https://arxiv.org/html/2604.07429v1#bib.bib21)], Qwen3-VL-30B-A3B [[8](https://arxiv.org/html/2604.07429v1#bib.bib21)], and UI-TARS-1.5-7B [[57](https://arxiv.org/html/2604.07429v1#bib.bib30)].

For all models, we use the same paused evaluation protocol under a shared runtime and verifier: the game is paused during inference so that scores reflect decision quality rather than response speed. Each model outputs one interaction command per step with a fixed per-action execution duration (usually 200–500 ms, depending on the game), and a maximum budget of 100 actions per task. During the interactions, all metrics are continuously computed from verifiable game state by the evaluator defined in Section [3.5](https://arxiv.org/html/2604.07429v1#S3.SS5 "3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"). The exact model-side output-format prompts used in these evaluations are listed in Appendix [12.3](https://arxiv.org/html/2604.07429v1#S12.SS3 "12.3 Model Output-Format Blocks ‣ 12 Prompt Templates and Game Prompt Blocks ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").

### 4.2 Main Results

Table 6: 
Main results on GameWorld across 34 games and 170 tasks. We report genre-level and overall 𝒮​ℛ\mathcal{SR} (Success Rate, %) and 𝒫​𝒢\mathcal{PG} (Progress, %) for 18 models (10 generalist multimodal agents and 8 computer-use agents). The final rank is determined by overall 𝒫​𝒢\mathcal{PG}.

|  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Model | Arcade | | Platformer | | Puzzle | | Runner | | Simulation | | Overall | | |
| 𝒮​ℛ\mathcal{SR} | 𝒫​𝒢\mathcal{PG} | 𝒮​ℛ\mathcal{SR} | 𝒫​𝒢\mathcal{PG} | 𝒮​ℛ\mathcal{SR} | 𝒫​𝒢\mathcal{PG} | 𝒮​ℛ\mathcal{SR} | 𝒫​𝒢\mathcal{PG} | 𝒮​ℛ\mathcal{SR} | 𝒫​𝒢\mathcal{PG} | 𝒮​ℛ\mathcal{SR} | 𝒫​𝒢\mathcal{PG} | Rank |
| Human | | | | | | | | | | | | | |
| Novice Player | 45.7 | 55.5 | 60.0 | 65.6 | 51.4 | 63.1 | 60.0 | 72.0 | 60.0 | 62.0 | 55.3 | 64.1 | – |
| Expert Player | 65.7 | 73.9 | 85.0 | 88.0 | 68.6 | 77.1 | 82.5 | 87.8 | 85.0 | 86.0 | 77.1 | 82.6 | – |
| Computer-Use Agents | | | | | | | | | | | | | |
| [Uncaptioned image] Claude-Sonnet-4.6 | 8.6 | 27.2 | 22.5 | 36.5 | 20.0 | 43.8 | 30.0 | 55.6 | 10.0 | 16.8 | 19.4 | 38.3 | 2 [Uncaptioned image] |
| [Uncaptioned image] Gemini-2.5-Computer-Use | 5.7 | 28.0 | 20.0 | 35.8 | 11.4 | 32.2 | 30.0 | 55.4 | 10.0 | 19.3 | 16.5 | 36.1 | 3 [Uncaptioned image] |
| [Uncaptioned image] OpenAI-Computer-Use | 5.7 | 24.7 | 17.5 | 31.3 | 20.0 | 45.8 | 27.5 | 53.0 | 5.0 | 12.0 | 16.5 | 35.8 | 4 |
| [Uncaptioned image] Qwen3-VL-Plus | 5.7 | 23.5 | 20.0 | 34.6 | 14.3 | 35.6 | 27.5 | 51.0 | 5.0 | 10.7 | 15.9 | 33.6 | 5 |
| [Uncaptioned image] Seed-1.8 | 8.6 | 31.1 | 25.0 | 40.3 | 25.7 | 52.0 | 27.5 | 50.6 | 5.0 | 11.0 | 20.0 | 39.8 | 1 [Uncaptioned image] |
| [Uncaptioned image] Qwen3-VL-235B-A22B | 5.7 | 23.2 | 22.5 | 35.2 | 8.6 | 29.7 | 25.0 | 51.0 | 0.0 | 1.7 | 14.1 | 31.4 | 6 |
| [Uncaptioned image] Qwen3-VL-30B-A3B | 8.6 | 26.8 | 20.0 | 31.9 | 2.9 | 27.6 | 25.0 | 50.3 | 0.0 | 2.2 | 12.9 | 30.8 | 8 |
| [Uncaptioned image] UI-TARS-1.5-7B | 5.7 | 31.4 | 15.0 | 24.4 | 5.7 | 29.9 | 27.5 | 52.4 | 0.0 | 3.8 | 12.4 | 31.1 | 7 |
| Generalist Multimodal Agents | | | | | | | | | | | | | |
| [Uncaptioned image] Claude-Sonnet-4.6 | 5.7 | 28.3 | 22.5 | 37.0 | 25.7 | 51.5 | 30.0 | 51.9 | 15.0 | 16.6 | 20.6 | 39.3 | 3 [Uncaptioned image] |
| [Uncaptioned image] Gemini-3-Flash-Preview | 5.7 | 26.3 | 25.0 | 41.2 | 25.7 | 54.8 | 32.5 | 55.4 | 10.0 | 21.1 | 21.2 | 41.9 | 1 [Uncaptioned image] |
| [Uncaptioned image] GLM-4.6V | 8.6 | 22.8 | 20.0 | 33.9 | 5.7 | 29.1 | 27.5 | 49.1 | 0.0 | 5.3 | 14.1 | 30.8 | 8 |
| [Uncaptioned image] GPT-5.2 | 8.6 | 29.3 | 22.5 | 36.7 | 28.6 | 56.2 | 27.5 | 52.6 | 10.0 | 16.9 | 20.6 | 40.6 | 2 [Uncaptioned image] |
| [Uncaptioned image] Grok-4.1-Fast-Reasoning | 8.6 | 23.7 | 22.5 | 37.3 | 14.3 | 46.6 | 25.0 | 49.0 | 5.0 | 10.4 | 16.5 | 36.0 | 6 |
| [Uncaptioned image] Kimi-K2.5 | 8.6 | 26.4 | 20.0 | 35.3 | 25.7 | 51.4 | 27.5 | 49.7 | 5.0 | 11.7 | 18.8 | 37.4 | 5 |
| [Uncaptioned image] Qwen3-VL-Plus | 8.6 | 25.6 | 22.5 | 37.8 | 14.3 | 39.1 | 27.5 | 51.1 | 0.0 | 10.0 | 16.5 | 35.4 | 7 |
| [Uncaptioned image] Seed-1.8 | 11.4 | 33.5 | 22.5 | 34.6 | 22.9 | 48.7 | 27.5 | 51.2 | 10.0 | 18.8 | 20.0 | 39.0 | 4 |
| [Uncaptioned image] Qwen3-VL-235B-A22B | 5.7 | 23.2 | 17.5 | 29.5 | 8.6 | 33.3 | 27.5 | 50.4 | 0.0 | 3.6 | 13.5 | 30.8 | 9 |
| [Uncaptioned image] Qwen3-VL-30B-A3B | 2.9 | 20.3 | 20.0 | 36.5 | 2.9 | 26.1 | 27.5 | 51.1 | 0.0 | 3.5 | 12.4 | 30.6 | 10 |

##### Metric Definitions.

Let ℛ\mathcal{R} be the set of evaluated runs and let N=|ℛ|N=|\mathcal{R}|. For run ii, let qi,tq\_{i,t} denote the task score read from verifiable game state at step tt. In the runtime, qi,tq\_{i,t} is defined either by a configured scalar score field or by the sum of configured aggregate score fields. Let bib\_{i} be the starting score of each task, τi\tau\_{i} the configured task target score, and qimax=maxt⁡qi,tq\_{i}^{\max}=\max\_{t}q\_{i,t} the best score observed in the run. By construction, benchmark tasks satisfy τi>bi\tau\_{i}>b\_{i}. The run-level progress is then:

|  |  |  |  |
| --- | --- | --- | --- |
|  | progressi=clip[0,1]⁡(qimax−biτi−bi).\mathrm{progress}\_{i}=\operatorname{clip}\_{[0,1]}\!\left(\frac{q\_{i}^{\max}-b\_{i}}{\tau\_{i}-b\_{i}}\right). |  | (1) |

When reset-on-fail is enabled, episode-local score tracking is cleared after each reset, but the run-level best progress is preserved. Therefore, progressi\mathrm{progress}\_{i} measures the furthest normalized progress reached within the fixed step budget, rather than only the final episode before termination. Finally, for each model, we report the averaged 𝒮​ℛ\mathcal{SR} and 𝒫​𝒢\mathcal{PG} over all runs:

|  |  |  |  |
| --- | --- | --- | --- |
|  | 𝒮ℛ=1N∑i=1N𝟏[statusi=success],𝒫𝒢=1N∑i=1Nprogressi\mathcal{SR}=\frac{1}{N}\sum\_{i=1}^{N}\mathbf{1}[\mathrm{status}\_{i}=\texttt{success}],\quad\mathcal{PG}=\frac{1}{N}\sum\_{i=1}^{N}\mathrm{progress}\_{i} |  | (2) |

For better readability, both metrics are reported in percentage form in Table [6](https://arxiv.org/html/2604.07429v1#S4.T6 "Table 6 ‣ 4.2 Main Results ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").

![Refer to caption](https://arxiv.org/html/2604.07429v1/by_task_heatmap.png)


Figure 3: 
Per-game progress heatmap across the GameWorld benchmark. Rows correspond to 18 evaluated game agents with model: (a) Claude-Sonnet-4.6, (b) Gemini-2.5-Computer-Use, (c) OpenAI-Computer-Use, (d) Qwen3-VL-Plus, (e) Seed-1.8, (f) Qwen3-VL-235B-A22B, (g) Qwen3-VL-30B-A3B, (h) UI-TARS-1.5-7B, (i) Claude-Sonnet-4.6, (j) Gemini-3-Flash-Preview, (k) GLM-4.6V, (l) GPT-5.2, (m) Grok-4.1-Fast-Reasoning, (n) Kimi-K2.5, (o) Qwen3-VL-Plus, (p) Seed-1.8, (q) Qwen3-VL-235B-A22B, and (r) Qwen3-VL-30B-A3B. (a)-(h) are Computer-Use Agents and (i)-(r) are Generalist Multimodal Agents. Colors represent average task progress for each game from *high (green)* to *medium (yellow)* to *low (red)*.

##### Agent Performance.

Table [6](https://arxiv.org/html/2604.07429v1#S4.T6 "Table 6 ‣ 4.2 Main Results ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") summarizes performance for 18 model–interface pairs, ranked by overall 𝒫​𝒢\mathcal{PG}.
Overall performance remains far from satisfactory. Among Generalist agents, Gemini-3-Flash-Preview achieves the best overall 𝒫​𝒢=41.9\mathcal{PG}=41.9, followed by GPT-5.2 at 40.6; Claude-Sonnet-4.6 and Seed-1.8 reach 39.3 and 39.0, respectively. Among Computer-Use Agents, Seed-1.8 performs best at 39.8, with Claude-Sonnet-4.6 close behind. However, overall 𝒮​ℛ\mathcal{SR} remains relatively low (12.4–21.2%), indicating that models are often capable of making partial progress without meeting the full task target. To this end, our outcome-based state-verifiable evaluation provides a more fine-grained task-progress signal, making it possible to distinguish partial advancement from full completion and to diagnose capability gaps beyond binary task success rate.

Figure [3](https://arxiv.org/html/2604.07429v1#S4.F3 "Figure 3 ‣ Metric Definitions. ‣ 4.2 Main Results ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") further visualizes per-game progress beyond genre averages. At the genre level, Runner games yield the highest progress for many models. Simulation tasks remain broadly challenging, with low success and progress for many models, highlighting the difficulty of open-ended objectives and longer-horizon state tracking.

##### Human Players.

We also conduct a human study with two computer-science post-graduate students. One had no prior exposure to the benchmark games or tasks, and we report this participant as the Novice Player. The other had studied all the game rules and practiced the controls beforehand, and we report this participant as the Expert Player. For better consistency, we use the same action budget as in the agent evaluation: each task is limited to 100 primitive actions (mouse clicks or key presses).

The performances of human players in Table [6](https://arxiv.org/html/2604.07429v1#S4.T6 "Table 6 ‣ 4.2 Main Results ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") show that, under the same action budget, the best current agents remain far below the Novice Player (55.3 𝒮​ℛ\mathcal{SR} / 64.1 𝒫​𝒢\mathcal{PG}), highlighting many challenges remain in building game agents for robust control, long-horizon planning, and reliable task completion.

### 4.3 Benchmark Robustness Under Repeated Evaluation

To test whether GameWorld behaves as a reproducible measurement platform rather than a one-off leaderboard snapshot, we perform repeated full-benchmark evaluation on two open-source backbones, Qwen3-VL-30B-A3B and Qwen3-VL-235B-A22B, each in both CUA and Generalist interfaces, yielding four model–interface pairs. Due to the cost of repeated full-benchmark runs, we restrict this validation study to these two open-source models. For each setting, we report mean ±\pm standard deviation over ten full-benchmark reruns.

Table 7: 
Repeat-averaged overall 𝒮​ℛ\mathcal{SR} and 𝒫​𝒢\mathcal{PG} for the four Qwen model–interface pairs used in the repeated-evaluation study. We report mean ±\pm standard deviation computed from the ten full-benchmark repeat averages.

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| Model | Agent Interface | Repeats | Overall 𝒮​ℛ\mathcal{SR} | Overall 𝒫​𝒢\mathcal{PG} |
| Qwen3-VL-30B-A3B | Computer-Use Agent | 10 | 12.7±\pm1.2 | 30.9±\pm1.1 |
| Qwen3-VL-30B-A3B | Generalist Agent | 10 | 12.5±\pm1.3 | 30.7±\pm1.1 |
| Qwen3-VL-235B-A22B | Computer-Use Agent | 10 | 13.8±\pm0.7 | 30.4±\pm0.7 |
| Qwen3-VL-235B-A22B | Generalist Agent | 10 | 13.6±\pm1.4 | 30.1±\pm0.5 |

Table [7](https://arxiv.org/html/2604.07429v1#S4.T7 "Table 7 ‣ 4.3 Benchmark Robustness Under Repeated Evaluation ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") summarizes the resulting overall statistics. The central observation is stability: across all four settings, the standard deviation of overall 𝒫​𝒢\mathcal{PG} remains in a low single-digit band, and the corresponding 𝒮​ℛ\mathcal{SR} variation is likewise limited. This indicates that the benchmark can reproduce the same broad performance level and capability trends across reruns, which is necessary if the platform is to serve as a meaningful test bed for game agents. At the same time, the repeated runs also set an interpretation boundary: very small differences between nearby systems should not be overstated without rerun-based evidence.

Figure 4: 
Per-game average progress across the 34 benchmark games for the four Qwen model–interface pairs used in the repeated-evaluation study. Each panel corresponds to one model–interface pair, and each horizontal bar shows the mean progress over the same ten full-benchmark reruns. Error bars denote one run-level standard deviation.

Figure [4](https://arxiv.org/html/2604.07429v1#S4.F4 "Figure 4 ‣ 4.3 Benchmark Robustness Under Repeated Evaluation ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") provides the corresponding per-game view. Most games show tight run-to-run bands, while visibly larger variance is concentrated in a limited subset of control-sensitive or high-difficulty games such as Hextris, Cubefield, Wordle, and World’s Hardest Game 2. This is the expected pattern for a robust benchmark: aggregate conclusions remain reproducible, while difficult games still expose meaningful differences in planning, control, and memory.

### 4.4 Capability-Aligned Curriculum Analysis

Genre-level averages alone cannot tell whether a failure is mainly caused by weak capabilities such as control grounding, reactive behavior, spatial navigation, or long-horizon reasoning. Therefore, for better interpretation, we conduct *diagnosis-driven analysis* to understand why models fail beyond genre-level result aggregation. We group the games into a five-level curriculum in which each level is anchored by its dominant capability bottleneck. The curriculum makes these patterns more interpretable across both Generalist and Computer-Use agents, and provides a diagnosable structure for improving future game agents.

Figure 5: 
Capability-aligned five-level curriculum profiles across agent interfaces and models.
Left: Generalist agents. Right: Computer-Use agents. Each radar axis corresponds to one curriculum level and values are average task progress of all the games in the level.

* •

  Level-1 (Basic Control and Timing Grounding): This level isolates whether an agent can reliably map visual observations to valid atomic interactions such as clicking, issuing a single key press, or waiting, and can trigger them at the appropriate moment under low strategic load. Since planning demands are intentionally light, failures here mainly indicate weak action grounding, poor visual perception, or weak basic timing judgment; games include 5-breakout, 8-core-ball, and 27-stack.
* •

  Level-2 (System-1 Reactive Control): This level emphasizes high-frequency reflexes in continuously evolving scenes where immediate reaction dominates over deliberate planning. Performance in level-2 reflects the agent’s sensitivity to latency, timing precision, and short-horizon motor stability; games include 4-boxel-rebound, 7-chrome-dino, 9-cubefield, 10-doodle-jump, 11-edge-surf, 13-flappy-bird, 14-geodash, 21-ns-shaft, 24-restless-wing-syndrome, 26-run-3, 28-temple-run-2, and 30-vex-3.
* •

  Level-3 (System-2 Spatial Navigation): This level mostly tests whether agents can model a 2D or 3D geometric world and use it for deliberate pathfinding in structured layouts. Underperformance here usually reflects weak spatial reasoning, waypoint sequencing, or unstable coordination between high-level intent and precise action; games include 2-another-gentlemans-adventure, 3-astray, 6-captaincallisto, 15-google-snake, 17-mario-game, 22-ovo, 23-pacman, 25-rocket-league-2d, 31-wolf3d, 33-worlds-hardest-game, and 34-worlds-hardest-game-2.
* •

  Level-4 (Symbolic Reasoning & Strategy): This level groups rule-intensive, discrete environments in which the bottleneck is strategy planning over a structured state space. Differences between this level and the control-oriented levels reveal the agent’s limitations in symbolic planning, rule tracking, and long-horizon decision consistency; games include 1-2048, 16-hextris, 19-minesweeper, 29-tetris, and 32-wordle.
* •

  Level-5 (Open-World Coordination & Management): This level captures the most open-ended settings in the current suite, where agents must coordinate navigation, interaction, and subgoal management in high-dimensional environments. Evaluation at this level usually reflects compounded failures in memory, policy stability, and error recovery; games include 12-fireboy-and-watergirl, 18-minecraft-clone-glm, and 20-monkey-mart.

Figure [5](https://arxiv.org/html/2604.07429v1#S4.F5 "Figure 5 ‣ 4.4 Capability-Aligned Curriculum Analysis ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") visualizes per-level progress under this curriculum for Generalist and Computer-Use agents. It can be observed that both interfaces exhibit a similar performance which peaks at Level 4 and 2, but drops sharply at Level 1 and 5. It suggests that game agents performs well in strategic decision making and reacting, as MLLMs always do in generic tasks, while long-horizon tasks and timing grounding still remaining bottleneck for game playing.

### 4.5 Challenges and Analyses: Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes

To expore the current limitation and future imporvement directions of game agents, we further examine real-time interaction, context-memory sensitivity, action validity, and interpretable failure modes. Beyond raw leaderboard metrics, these analysis dimensions highlight several future challenges for multimodal game agents.

|  |  |  |  |
| --- | --- | --- | --- |
| Model | Real-Time sec/step | 𝒮​ℛ\mathcal{SR} | 𝒫​𝒢\mathcal{PG} |
| Computer-Use Agents | | | |
| Qwen3-VL-235B-A22B | 6.2 | 17.1 | 33.2 |
| Qwen3-VL-30B-A3B | 2.4 | 15.6 | 33.0 |
| Generalist Multimodal Agents | | | |
| Qwen3-VL-235B-A22B | 6.4 | 16.8 | 34.0 |
| Qwen3-VL-30B-A3B | 3.4 | 15.6 | 32.9 |

Table 8: 
GameWorld-RT results for Qwen3-VL-30B-A3B and Qwen3-VL-235B-A22B in Generalist and CUA interfaces. In GameWorld-RT benchmark, the environment continues running during model inference. ‘RT sec/step’ is seconds per executed step.

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| Memory Rounds | Model | Input Tokens | sec/ step | 𝒫​𝒢\mathcal{PG} |
| 0 | Qwen3-VL-235B-A22B | 1278 | 5.5 | 30.0 |
|  | Qwen3-VL-235B-A22B-CUA | 1891 | 7.2 | 30.3 |
| 1 | Qwen3-VL-235B-A22B | 2171 | 6.8 | 30.1 |
|  | Qwen3-VL-235B-A22B-CUA | 3771 | 10.1 | 29.0 |
| 2 | Qwen3-VL-235B-A22B | 3052 | 8.6 | 30.6 |
|  | Qwen3-VL-235B-A22B-CUA | 5627 | 12.8 | 28.7 |

Table 9: 
Memory-round sensitivity across the full benchmark for Qwen3-VL-235B-A22B in Generalist and CUA interfaces. We vary memory rounds and report average input tokens, wall-clock sec/step, and overall 𝒫​𝒢\mathcal{PG}.

#### 4.5.1 GameWorld-RT: Real-Time Benchmark

Beyond the default paused-inference evaluation, we also establish GameWorld-RT as a separate benchmark variant for more realistic interactive evaluation. Real-time interaction is a critical dimension of digital-agent performance because many practical settings require agents to perceive, reason, and act under continuously evolving environmental dynamics. It also introduces a distinct and more deployment-faithful challenge: the agent must not only choose the right action, but do so quickly enough for that action to remain relevant when it is executed. In GameWorld-RT, the environment does not pause while the model is reasoning, so response latency becomes part of the task itself. Table [8](https://arxiv.org/html/2604.07429v1#S4.T8 "Table 8 ‣ 4.5 Challenges and Analyses:Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") reports Qwen3-VL-30B-A3B and Qwen3-VL-235B-A22B results on GameWorld-RT in both Generalist and CUA interfaces.

GameWorld-RT remains challenging across all four settings. The smaller 30B backbone is substantially faster, while the 235B backbone achieves slightly higher progress; however, success rates remain only in very low throughout, indicating that faster reaction alone does not solve the benchmark when the environment keeps running during inference. Real-time play therefore exposes a distinct difficulty in which reasoning speed and action timing are more tightly coupled.

We treat GameWorld-RT as complementary to the default paused benchmark. The paused setting isolates decision quality by removing response-time confounds, whereas GameWorld-RT captures a more real-world deployment-oriented setting in which reasoning, reaction time, and action timing are coupled. Note that results on GameWorld-RT should not be compared directly with those on the default paused benchmark, because in the real-time setting the game continues to evolve during model inference, so the effective gameplay duration includes reasoning time and is therefore longer under the same action budget.

#### 4.5.2 Context-Memory Sensitivity

We also analyze the memory-round ablation across the same 34-game benchmark. Table [9](https://arxiv.org/html/2604.07429v1#S4.T9 "Table 9 ‣ 4.5 Challenges and Analyses:Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") shows that increasing memory substantially raises both prompt length and wall-clock latency: the Generalist interface grows from about 1.3k to 3.1k input tokens and from 5.5 to 8.6 seconds per step, while the CUA interface grows from about 1.9k to 5.6k tokens and from 7.2 to 12.8 seconds per step. More importantly, the performance effect is inconsistent for the two interfaces: for the Generalist Agents, 𝒫​𝒢\mathcal{PG} rises modestly as memory rounds increase, while for the CUAs, performance steadily declines.

This split is plausible given the differences in action spaces. Generalist agents operate over semantic trajectories, so a longer history can preserve useful task context because the semantic content of each action is retained. CUA agents, by contrast, carry longer low-level action traces without semantic information, making their history harder to interpret jointly with the screenshot. This is more likely to accumulate distracting interaction details as memory grows. Since the time cost increases substantially in both interfaces, memory should be viewed as a selective benefit for game agents rather than a uniformly helpful module.

#### 4.5.3 Action Validity and Instruction Following

|  |  |
| --- | --- |
| Category | Example |
| No-Tool-Call  (NTC) | Model responses in natural language without tools:   # Model Output: The obstacle is coming from the left, so I should move left first. # Invalid Reason: The model does not generate an executable tool call but instead returns free-form natural language.   Malformed format due to truncation of very long reasoning:   # Model Output: "<think> I should first inspect the scene carefully before acting... </think> <tool\_call> {"name": "  # Invalid Reason: The tool-call block is never properly closed. |
| Out-of-Space  (OOS) | High-level actions requiring multiple steps are not allowed:   # Model Output: craft\_a\_workbench() # Invalid Reason: The model returns a plausible tool call, but this semantic action is not registered.   In a keyboard-only game where the control space is stated   explicitly in the game rules:   # Model Output: left\_click(x=512, y=384) # Invalid Reason: The CUA model calls a computer-use tool, but mouse clicking is outside the allowed control space. |

Table 10: 
Invalid-action categories and example model outputs.

|  |  |  |  |
| --- | --- | --- | --- |
| Model | IAR (%) | NTC (%) | OOS (%) |
| Computer-Use Agents | | | |
| Claude-Sonnet-4.6 | 0.0 | 0.0 | 0.0 |
| Gemini-2.5-Computer-Use | 0.0 | 0.0 | 0.0 |
| OpenAI-Computer-Use | 0.0 | 0.0 | 0.0 |
| Qwen3-VL-Plus | <0.1 | <0.1 | 0.0 |
| Seed-1.8 | 0.0 | 0.0 | 0.0 |
| Qwen3-VL-235B-A22B | <0.1 | <0.1 | 0.0 |
| Qwen3-VL-30B-A3B | <0.1 | <0.1 | 0.0 |
| UI-TARS-1.5-7B | 0.4 | <0.1 | 0.4 |
| Generalist Multimodal Agents | | | |
| Claude-Sonnet-4.6 | 0.0 | 0.0 | 0.0 |
| Gemini-3-Flash-Preview | 0.0 | 0.0 | 0.0 |
| GLM-4.6V | 8.3 | 7.6 | 0.7 |
| GPT-5.2 | 0.0 | 0.0 | 0.0 |
| Grok-4.1-Fast-Reasoning | <0.1 | <0.1 | 0.0 |
| Kimi-K2.5 | 0.0 | 0.0 | 0.0 |
| Qwen3-VL-Plus | <0.1 | <0.1 | 0.0 |
| Seed-1.8 | 0.0 | 0.0 | 0.0 |
| Qwen3-VL-235B-A22B | <0.1 | <0.1 | 0.0 |
| Qwen3-VL-30B-A3B | 2.7 | 2.7 | <0.1 |
| Overall Mean | 0.8 | 0.8 | 0.0 |

Table 11: 
Invalid Action Rate (IAR) across all evaluated agents, broken down into No-Tool-Call (NTC) and Out-of-Space (OOS), i.e., IAR=No​Call+OOS\mathrm{IAR}=\mathrm{No\penalty\ Call}+\mathrm{OOS}.

Agents cannot act in a free-form manner in interactive environments; they must obey role-specific control constraints and action-space rules at every step.
Beyond the main benchmark metrics, invalid-action statistics remain useful as a lightweight reliability signal.
Invalid Action Rate (IAR) is the fraction of proposed actions that fail tool-call parsing, role constraints, or parser checks.

|  |  |  |  |
| --- | --- | --- | --- |
|  | IAR=1−∑r∈ℛ#​valid​\_​actions​(r)∑r∈ℛ#​proposed​\_​actions​(r).\mathrm{IAR}=1-\frac{\sum\_{r\in\mathcal{R}}\#\mathrm{valid\\_actions}(r)}{\sum\_{r\in\mathcal{R}}\#\mathrm{proposed\\_actions}(r)}. |  | (3) |

We therefore treat lower IAR (Eq. 2) as a direct instruction-following proxy. Specifically, to further understand the sources, we separate invalid actions into two categories:

* •

  No-Tool-Call (NTC) means the model does not emit any executable tool call at all, typically because overly long thinking leads to truncation or because the final output does not satisfy the required tool-call formatting. In practice, this often appears either as free-form natural-language output with no tool invocation, or as an unfinished tool-call block that failed to be parsed.
* •

  Out-of-Space (OOS) means the model does return a tool call, but the call falls outside the legal action space: for example, a CUA may request a forbidden key or mouse operation, a generalist agent may emit an unregistered action, or the tool call may omit required arguments or provide malformed parameters.

Table [10](https://arxiv.org/html/2604.07429v1#S4.T10 "Table 10 ‣ 4.5.3 Action Validity and Instruction Following ‣ 4.5 Challenges and Analyses:Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") shows representative invalid-action categories with placeholder outputs, and Table [11](https://arxiv.org/html/2604.07429v1#S4.T11 "Table 11 ‣ 4.5.3 Action Validity and Instruction Following ‣ 4.5 Challenges and Analyses:Real-Time Interaction, Context-Memory Sensitivity, Action Validity, and Failure Modes ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") reports the aggregate invalid-action breakdowns. Appendix [11.2](https://arxiv.org/html/2604.07429v1#S11.SS2 "11.2 Low-Level Action and Validation ‣ 11 Agent Details ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") further details the low-level legality checker. Overall, under long interactive contexts, weaker models are more likely to forget the available action space and emit non-executable or non-permitted tool calls.

#### 4.5.4 Failure Modes and Analysis

We identify four task-failure categories that are useful for understanding game agents’ performance in the case study:
Instruction-following, Perception, Fine-grained action, and Long-horizon memory.

##### Perception failures.

The agent misreads visual state (objects, UI cues, or spatial layout) of the game, causing incorrect action decisions. These errors are often visible in the model’s intermediate reasoning process, for example when it incorrectly identifies the position of obstacles or misjudges the traversable region of a map. Such errors are particularly pronounced in cluttered scenes or under partial observability, where fine-grained visual discrimination is required.

##### Fine-grained action failures.

The high-level intent is correct but low-level execution is mistimed or imprecise (e.g., jump timing, key-combo duration). Even when the model correctly understands the current game state, it may still fail to choose or execute the right action for that state, often because it does not fully capture the game mechanics or the effect of its own actions. These failures highlight the gap between strategic reasoning and the precise motor-level control demanded by real-time gameplay.

##### Instruction-following failures.

The agent proposes actions that violate declared controls, output schema, or task-level action constraints. In some cases, the agent ignores specific parts of the user instruction. Under longer interaction trajectories, it may even drift away from the final task objective and start executing irrelevant or unproductive behaviors. This typically manifests as invalid key bindings, malformed action outputs, or attempts to invoke unavailable mechanics.

##### Long-horizon memory failures.

The agent loses critical historical context, repeats ineffective loops, or fails to preserve multi-step plans. This behavior is especially common in weaker base models, where the agent may repeatedly issue the same ineffective action, receive no useful feedback, and enter a loop without self-correction. This reflects fundamental limitations in the agent’s ability to maintain coherent goal representations across extended interaction horizons.

## 5 Case Study

We provide three case studies to illustrate the interaction of game agents with the environment. Each case is presented through 5 key frames together with a short reasoning summary, the proposed and executed action, and the corresponding verifiable state change from gameAPI.

### 5.1 Game Agent Interface Comparison: Generalist Agent vs. CUA

To better illustrate the differences of two game agent interfaces, we firstly present an example of a shared task accoss CUA and Generalist agents. Figure [6](https://arxiv.org/html/2604.07429v1#S5.F6 "Figure 6 ‣ 5.1 Game Agent Interface Comparison: Generalist Agent vs. CUA ‣ 5 Case Study ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") shows matched trajectories of Mario-Game under CUA and Generalist interfaces. With the same model backbone and game environment, the difference only existing in control interface: CUA emits low-level keyboard and mouse actions directly, while the Generalist follows a richer semantic plan and produces semantic actions.

![Refer to caption](https://arxiv.org/html/2604.07429v1/x1.png)


Figure 6: Case-study visualization for game-agent interface comparison. This Mario page stacks a matched CUA trajectory above a Generalist trajectory so that their divergence can be attributed to the action interface rather than the backbone.

![Refer to caption](https://arxiv.org/html/2604.07429v1/x2.png)


Figure 7: Case-study visualization for long-horizon simulation and resource collection. This Minecraft Clone trajectory shows locally plausible interactions that advance the progress, but still fail to fully meet the task target.

![Refer to caption](https://arxiv.org/html/2604.07429v1/x3.png)


Figure 8: Case-study visualization for real-time reaction and timing control. This Flappy Bird window shows how a visually small timing error can still be mechanically decisive under tight control constraints.

### 5.2 Long-Horizon Simulation: Minecraft Resource Collection

Figure [7](https://arxiv.org/html/2604.07429v1#S5.F7 "Figure 7 ‣ 5.1 Game Agent Interface Comparison: Generalist Agent vs. CUA ‣ 5 Case Study ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") shows an open-ended trajectory of Minecraft-Clone-GLM, in which the agent repeatedly mines the resource toward the target number. The failure is not instruction-following but missing closure: the run reaches 90% progress yet still fails to finish the collection target within the step limit.

### 5.3 Real-Time Reaction and Timing Control: Flappy Bird

As shown in Figure [8](https://arxiv.org/html/2604.07429v1#S5.F8 "Figure 8 ‣ 5.1 Game Agent Interface Comparison: Generalist Agent vs. CUA ‣ 5 Case Study ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"), the third case uses a short Flappy-Bird interaction sequence. The consecutive frames look nearly identical, while the correct action alternates between waiting and flapping. This highlights the real-time control difficulty of video games: a slightly early or late flap determines whether any progress should be inferred from visually similar states.

## 6 Related Work

### 6.1 Computer-Use Benchmarks with Online Environments

Computer-use has emerged as a major direction in the recent rise of digital agents and serves as an important testbed for advancing agent capabilities. Its core challenge lies in designing a standardized action space and interactive environment that allow agents to flexibly control complex interfaces and operations. The design of these benchmarks largely determines how effectively agents can assist with human computer tasks and whether they can support increasingly complex and diverse workflows.
WebArena [[86](https://arxiv.org/html/2604.07429v1#bib.bib20)] and OSWorld [[75](https://arxiv.org/html/2604.07429v1#bib.bib10)] establish strong templates for agent benchmarking in browser and desktop environments, highlighting the importance of outcome-based evaluation. Cradle [[64](https://arxiv.org/html/2604.07429v1#bib.bib32)] and early studies of computer-use agents [[21](https://arxiv.org/html/2604.07429v1#bib.bib35), [82](https://arxiv.org/html/2604.07429v1#bib.bib34), [34](https://arxiv.org/html/2604.07429v1#bib.bib33), [25](https://arxiv.org/html/2604.07429v1#bib.bib36)] further demonstrate that foundation models can operate general-purpose GUIs, even professional softwares or complex games. OSWorld-MCP [[38](https://arxiv.org/html/2604.07429v1#bib.bib11)] extends this line by highlighting fairness issues in hybrid action pathways and tool-use decision quality. These computer-use benchmarks provide important guidance for making agent evaluation more standardized and scalable. GameWorld transfers these insights to game-agent evaluation through interactive environments, parallel instances, and outcome-based, state-verifiable evaluation.

### 6.2 Video Game Benchmarks for LLM and MLLM Agents

Game environments have long served as AI testbeds [[16](https://arxiv.org/html/2604.07429v1#bib.bib51), [11](https://arxiv.org/html/2604.07429v1#bib.bib45), [10](https://arxiv.org/html/2604.07429v1#bib.bib50), [77](https://arxiv.org/html/2604.07429v1#bib.bib52)]. In open-ended vision-centric games, early work focuses on training and agent construction: MineDojo [[23](https://arxiv.org/html/2604.07429v1#bib.bib37)] supplies internet-scale knowledge for Minecraft, VPT [[9](https://arxiv.org/html/2604.07429v1#bib.bib39)] learns behavioral priors from unlabeled gameplay video, Steve-1 [[42](https://arxiv.org/html/2604.07429v1#bib.bib47)] generates text-conditioned behaviors, JARVIS-1 [[71](https://arxiv.org/html/2604.07429v1#bib.bib44)] adds multimodal memory for long-horizon Minecraft tasks, See and Think [[81](https://arxiv.org/html/2604.07429v1#bib.bib48)] combines vision, language instruction, and code actions in Minecraft, and Voyager [[69](https://arxiv.org/html/2604.07429v1#bib.bib40)] demonstrates lifelong skill acquisition through LLM planning. More recent work also uses gameplay itself as a learning signal rather than only an evaluation target: Game-RL [[68](https://arxiv.org/html/2604.07429v1#bib.bib12)] synthesizes verifiable game tasks for RL, while Play to Generalize [[76](https://arxiv.org/html/2604.07429v1#bib.bib14)] shows that post-training on arcade-style gameplay can transfer to broader multimodal reasoning benchmarks. As models grow more capable, the bottleneck shifts from training to reliable evaluation. MCU [[84](https://arxiv.org/html/2604.07429v1#bib.bib17)] scales open-ended Minecraft evaluation through compositional atomic tasks and human-aligned assessment. LMGame-Bench [[33](https://arxiv.org/html/2604.07429v1#bib.bib3)] exposes prompt sensitivity by modularly toggling perception, memory, and reasoning. BALROG [[51](https://arxiv.org/html/2604.07429v1#bib.bib15)], LVLM-Playground [[70](https://arxiv.org/html/2604.07429v1#bib.bib13)], and V-MAGE [[83](https://arxiv.org/html/2604.07429v1#bib.bib19)] stress long-horizon, structured, or vision-centric reasoning in interactive games. VideoGameBench [[79](https://arxiv.org/html/2604.07429v1#bib.bib4)] shows that inference latency dominates real-time failure and introduces a paused track to isolate it. FlashAdventure [[3](https://arxiv.org/html/2604.07429v1#bib.bib1)] focuses on full-story-arc completion in 34 Flash adventure games and introduces CUA-as-a-Judge for automated milestone verification. Orak [[53](https://arxiv.org/html/2604.07429v1#bib.bib5)] provides a fine-tuning pipeline with held-out cross-game transfer studies. Specialized benchmarks further target collaboration or downstream workflows: Collab-Overcooked [[61](https://arxiv.org/html/2604.07429v1#bib.bib49)] evaluates language-mediated multi-agent coordination, while VideoGameQA-Bench [[62](https://arxiv.org/html/2604.07429v1#bib.bib16)] measures game QA tasks such as visual regression, glitch detection, and bug-report generation.
Notably, concurrent work GameVerse [[80](https://arxiv.org/html/2604.07429v1#bib.bib18)] shares our core idea of combining semantic and GUI control in a dual action space, and further introduces a reflect-and-retry protocol based on failure trajectories and tutorials. However, it still faces challenges in heuristic evaluation with using VLMs to quantify progress.

### 6.3 Game Agents and Scalable Infrastructure

Generalist agents can already accomplish a wide range of tasks in digital worlds. To move toward real-world embodied agents, researchers increasingly test agent capabilities in games and simulated environments.
A parallel line of work builds generalist agents that operate across many games. Game-TARS [[72](https://arxiv.org/html/2604.07429v1#bib.bib6)] anchors all actions to native keyboard-mouse inputs, while Jarvis-VLA [[41](https://arxiv.org/html/2604.07429v1#bib.bib43)] shows that large vision-language models can be post-trained to act directly through the same interface. WebGym [[7](https://arxiv.org/html/2604.07429v1#bib.bib2)] scales training environments to 300K realistic web tasks, showing that environment diversity directly improves out-of-distribution agent performance. NitroGen [[43](https://arxiv.org/html/2604.07429v1#bib.bib7)] extracts action labels from internet-scale gameplay video and wraps games with a universal Gym-style API [[12](https://arxiv.org/html/2604.07429v1#bib.bib46)]. Lumine [[63](https://arxiv.org/html/2604.07429v1#bib.bib38)] unifies perception, reasoning, and action in one vision-language model that transfers across 3D open worlds with game-specific fine-tuning. The SIMA project evolves from instruction-following across many simulated worlds in SIMA [[60](https://arxiv.org/html/2604.07429v1#bib.bib9)] to the richer interactive-partner setting of SIMA 2 [[59](https://arxiv.org/html/2604.07429v1#bib.bib8)], with held-out-environment evaluation and broader user interaction. As these game agents of different interfaces mature, standardized benchmarks become essential for measuring their performance. To this end, GameWorld provides a comprehensive benchmark with diverse games and tasks under a unified and verifiable evaluation protocol.

## 7 Conclusion

##### Discussion.

Our results show that current multimodal game agents can often make partial progress, yet still struggle to convert that progress into reliable task completion across diverse browser games. Under one shared runtime and verifier, GameWorld further exposes interface-conditioned weaknesses in real-time interaction, context-memory sensitivity, and action validity. These findings suggest that stronger game agents will require not only better reasoning, but also more reliable action grounding, more useful trajectory memory, and greater robustness to latency. We hope GameWorld serves as a reproducible benchmark for measuring such progress under standardized, outcome-based state-verifiable evaluation.

##### Limitations and Future Work.

The benchmark necessitates designing unique instruction sets for each new environment, which tightly couples the action space to the task and constrains the model’s scalability. Automating the producing and alignment process of Semantic Action Parsing through MLLM-powered agent exploration is left for future work. Further discussions, including the guideline on licensing and compliance of our benchmark and the cost summary, are detailed in Appendix [13](https://arxiv.org/html/2604.07429v1#S13 "13 Costs and Licensing Considerations ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").

##### Conclusion.

GameWorld provides a standardized and verifiable benchmark for evaluating multimodal game agents in browser environments. Across 34 games, 170 tasks, and 18 model–interface pairs, our results show that current agents can often make meaningful partial progress yet remain far from reliable task completion and human-level performance. Together with robustness, real-time, context-memory, and action-validity analyses, these findings establish GameWorld as a reproducible foundation for studying multimodal agents in complex, open-ended interactive environments.

\beginappendix

## 8 Benchmark Runtime

### 8.1 Preset Configuration

Each standalone benchmark run is launched using a registry preset passed via the command-line flag --config. The preset has the form:

<game\_id>+<task\_id>+<model\_spec>

where the three components are resolved independently and then composed into a concrete runtime configuration:

* •

  <game\_id>: contributes game rules, role definitions, low-level control constraints, and semantic action definitions.
* •

  <task\_id>: contributes the task instruction, evaluator configuration, target metrics, maximum step budget, and optional URL suffixes.
* •

  <model\_spec>: contributes the model identifier(s), provider-specific overrides, prompt template, and output-format prompts.

This decomposition keeps game definitions, tasks, and model profiles reusable and flexible: changing a task or swapping models does not require duplicating the underlying game configuration.

### 8.2 Suite Runner

The suite runner reads a suite YAML file and expands each benchmark case into explicit runs by enumerating the specified games, tasks, and models. The resulting preset for each child run reuses the same syntax as standalone execution in Section [8.1](https://arxiv.org/html/2604.07429v1#S8.SS1 "8.1 Preset Configuration ‣ 8 Benchmark Runtime ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"). Expanded runs are grouped into repeat waves. Within each wave, the runner launches up to --max-parallel child processes in parallel. Each child process invokes a standalone benchmark run with a dedicated port, a unique session ID, and an isolated run directory that stores logs and task-evaluation outputs. After all runs finish, the runner writes per-model summary files that support both interactive monitoring and subsequent aggregate analysis.

## 9 Observation-Action-Evaluation Loop

### 9.1 Runtime Coordinator

The benchmark loop is coordinated by a Runtime Coordinator.
Each MLLM is wrapped in an Agent object with an agent ID, model type, model client, role-specific controls, a semantic-control map, and a step counter.
The runtime also instantiates a GameEnv for the browser environment and the playable game, together with an Evaluator for task-progress tracking and evaluation.

At a high level, each interaction round executes the following sequence:

1. 1.

   Capture a screenshot of the current game environment.
2. 2.

   Optionally pause the game during model inference.
3. 3.

   Get the raw response from the model using the current screenshot and the assembled prompt template.
4. 4.

   Resume the game if paused.
5. 5.

   Parse the raw model output into an executable action payload.
6. 6.

   Execute the action in the browser environment.
7. 7.

   Capture a verifiable game-state snapshot.
8. 8.

   Evaluate task progress and check stopping or resetting conditions.

### 9.2 Evaluator and Reset-on-Fail

Evaluator. The evaluator receives the current state snapshot, global step index, maximum step budget, target threshold, and accumulated metrics.
It combines four stop or reset signals:

* •

  terminal status from state.terminal,
* •

  exhaustion of the fixed step budget,
* •

  reaching the task target score, and
* •

  any task-specific end-field rule.

Reset-on-Fail. If continue\_on\_fail is enabled and the game reports a terminal failure, the runtime does not end the run immediately.
Instead, it calls gameAPI.reset() to reset the task, allocates a new episode ID, waits for the game to become initialized again, and continues under the same global step budget.

## 10 Browser Sandbox and Game API

### 10.1 Browser Management

The GameLauncher starts a local HTTP server and serves the game HTML.
The browser manager then launches Chromium with a fixed viewport and disables common background-throttling behaviors. It also injects a dynamic speed-control script and a deterministic-randomness script by overriding JavaScript headers. Screenshots are captured through the Chrome DevTools Protocol rather than through a standard page-screenshot call to avoid visible flashing in headed mode. The browser-environment initialization process includes:

* •

  Start the environment and open the game in Chromium.
* •

  Wait until the game becomes actionable under the readiness gate described in Section [10.2](https://arxiv.org/html/2604.07429v1#S10.SS2 "10.2 Readiness Gate ‣ 10 Browser Sandbox and Game API ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").

### 10.2 Readiness Gate

Before the first agent action and after every reset, the runtime waits until the game reports an actionable state. The default actionable statuses are ready and playing. Table [12](https://arxiv.org/html/2604.07429v1#S10.T12 "Table 12 ‣ 10.2 Readiness Gate ‣ 10 Browser Sandbox and Game API ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") lists the common status values consumed by the readiness gate and the evaluator.

Table 12: Status values consumed by the readiness gate and evaluator.

|  |  |
| --- | --- |
| Status | Runtime description |
| loading | Assets or engine bootstrap are not yet ready for model control. |
| menu | The game is initialized but still in a pre-play state such as title screen, level select, or pause menu. |
| ready | The game is initialized and ready to begin, but may still require one trusted start action. |
| playing | The gameplay loop is active and safe for model control. |
| paused | The game is temporarily paused; this status is used by the sandbox pause mechanism during model inference. |
| terminal | The current in-game episode has ended. |

### 10.3 Verifiable State: Game API Schema

To enable verifiable evaluation, every benchmark game is required to expose a serializable window.gameAPI with three callable methods:
init(config), reset(options), and getState().
The returned state contains a game ID, a timestamp, lifecycle status, terminal metadata, a structured game\_state object, task metrics, and raw game-specific details. This serves as the verifiable game state for the outcome-based evaluation.

Here we provide an example Game API schema from 17\_mario-game. The exact game-specific fields can vary, but the top-level contract remains the same across all games in the GameWorld benchmark.

[⬇](data:text/plain;base64,ewogICAgImdhbWVJZCI6ICIxN19tYXJpby1nYW1lIiwKICAgICJzZWVkIjogNDIsCiAgICAidGltZXN0YW1wTXMiOiAxNzYwMDAxMjM0NTY3LAogICAgImdhbWVUaW1lTXMiOiAxODQyMCwKICAgICJzdGF0dXMiOiAicGxheWluZyIsCiAgICAidGVybWluYWwiOiB7CiAgICAgICAgImlzVGVybWluYWwiOiBmYWxzZSwKICAgICAgICAib3V0Y29tZSI6IG51bGwsCiAgICAgICAgInJlYXNvbiI6IG51bGwKICAgIH0sCiAgICAiZ2FtZV9zdGF0ZSI6IHsKICAgICJzY29yZSI6IDMyMDAsCiAgICAibGV2ZWwiOiAiMS0xIiwKICAgICJwcm9ncmVzcyI6IDAuMzcsCiAgICAicGxheWVyIjogewogICAgICAgICJ4IjogMTI4LAogICAgICAgICJ5IjogODAsCiAgICAgICAgInZ4IjogMCwKICAgICAgICAidnkiOiAwLAogICAgICAgICJwb3dlciI6IDEsCiAgICAgICAgImFsaXZlIjogdHJ1ZSwKICAgICAgICAibmFtZSI6ICJNYXJpbyIKICAgIH0sCiAgICAiYm9hcmQiOiBudWxsLAogICAgImVudGl0aWVzIjogbnVsbAogICAgfSwKICAgICJtZXRyaWNzIjogewogICAgICAgICJsaXZlcyI6IDMsCiAgICAgICAgImNvaW5zIjogOCwKICAgICAgICAiZGlzdGFuY2UiOiAzMjAwLAogICAgICAgICJhdHRlbXB0cyI6IDEsCiAgICAgICAgInRpbWVfbGVmdF9zIjogOTk5LAogICAgICAgICJlbmVtaWVzX2FsaXZlIjogNSwKICAgICAgICAibGV2ZWxfcHJvZ3Jlc3NfcGVyY2VudCI6IDQyCiAgICB9LAogICAgInJhdyI6IHsKICAgICAgICAid29ybGQiOiAxLAogICAgICAgICJzdGFnZSI6IDEsCiAgICAgICAgImxldmVsSWQiOiAiMS0xIiwKICAgICAgICAid29ybGREaXNwbGF5IjogIjEtMSIsCiAgICAgICAgImNvaW5zIjogOCwKICAgICAgICAiY29pbnNDb2xsZWN0ZWQiOiA4LAogICAgICAgICJsaXZlcyI6IDMsCiAgICAgICAgInRpbWVMZWZ0IjogOTk5LAogICAgICAgICJtYXBUaW1lIjogOTk5LAogICAgICAgICJwYXVzZWQiOiBmYWxzZSwKICAgICAgICAicGxheWVyUG93ZXIiOiAxLAogICAgICAgICJwbGF5ZXJOYW1lIjogIk1hcmlvIiwKICAgICAgICAibGV2ZWxQcm9ncmVzcyI6IDAuMzcsCiAgICAgICAgImxldmVsUHJvZ3Jlc3NQZXJjZW50IjogMzcKICAgIH0KfQ==)

{

"gameId": "17\_mario-game",

"seed": 42,

"timestampMs": 1760001234567,

"gameTimeMs": 18420,

"status": "playing",

"terminal": {

"isTerminal": false,

"outcome": null,

"reason": null

},

"game\_state": {

"score": 3200,

"level": "1-1",

"progress": 0.37,

"player": {

"x": 128,

"y": 80,

"vx": 0,

"vy": 0,

"power": 1,

"alive": true,

"name": "Mario"

},

"board": null,

"entities": null

},

"metrics": {

"lives": 3,

"coins": 8,

"distance": 3200,

"attempts": 1,

"time\_left\_s": 999,

"enemies\_alive": 5,

"level\_progress\_percent": 42

},

"raw": {

"world": 1,

"stage": 1,

"levelId": "1-1",

"worldDisplay": "1-1",

"coins": 8,

"coinsCollected": 8,

"lives": 3,

"timeLeft": 999,

"mapTime": 999,

"paused": false,

"playerPower": 1,

"playerName": "Mario",

"levelProgress": 0.37,

"levelProgressPercent": 37

}

}

This example illustrates the benchmark convention: game\_state stores structured in-game state for evaluation, metrics stores compact comparable counters, and raw preserves optional game-specific details for further analysis.

## 11 Agent Details

### 11.1 Rolling Memory

The base client supports a rolling memory store. The memory module records each interaction round in the fixed order:
user\_prompt →\rightarrow screenshot →\rightarrow reasoning →\rightarrow action.
At inference time, the client reinjects a filtered slice of the most recent rounds according to memory\_rounds, memory\_format, and memory\_include\_fields. Text entries are inserted under an Action History header, while screenshot entries are reattached as multimodal image items, so the resulting memory context is an interleaved multimodal history rather than a pure text block.

### 11.2 Low-Level Action and Validation

Low-Level Action Normalization. All executable actions are normalized before they reach Playwright. The runtime-facing normalized action schema handled by the executor consists of:

* •

  mouse actions: click, click\_hold, drag, mouse\_move, scroll;
* •

  keyboard actions: type, press\_key, press\_keys;
* •

  timing action: wait.

Table [1](https://arxiv.org/html/2604.07429v1#S2.T1 "Table 1 ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") defines the conceptual unified control space in terms of atomic events. The current implementation introduces a slightly higher-level normalized runtime action layer above that space for parser compatibility, legality checks, and one-action-per-step execution. Variants such as left\_click, right\_click, and left\_click\_hold are first normalized into this shared schema. During execution, the normalized actions are then translated into Playwright mouse and keyboard primitives such as button down/up, key down/up, wheel, move, and type events. This extra layer is also pragmatic because Playwright itself already exposes several higher-level interaction primitives. Thus the atomic event space remains the execution-layer semantics, while the runtime interface used inside the repository is slightly higher-level.

Action Legality Validation. Legality is role-aware and strictly configured by the role definition.
For generalist agents, the runtime coordinator first checks whether the proposed semantic control resolves against the registered semantic-control map, and then the executor checks whether the mapped low-level action satisfies the current role controls. For computer-use agents, the executor validates the proposed low-level action directly. The role controls come from the registry definition, including allowed\_keys, allow\_clicks, hold\_duration, and key\_durations. Invalid tool calls or disallowed low-level actions are logged as invalid and ignored at execution time. Key aliases are normalized (for example, left to ArrowLeft), and the executor can fall back to naming conventions when the requested key is not legal but has a semantically equivalent allowed key.
This makes the action interface more robust without expanding the legal action space beyond the role definition.

### 11.3 Semantic Action Parsing

Generalist agents do not emit raw keyboard or mouse actions directly.
Instead, they emit a semantic control payload whose control identifier can arrive as action, tool\_name, or tool\_id, together with runtime arguments. The runtime resolves this identifier through a registry-built semantic-control map with case-insensitive and alias-aware lookup, merges the runtime arguments into the YAML-defined binding, and applies optional cell\_bindings when a semantic cell reference should expand into coordinates. The mapped result then enters the same low-level execution chain as computer-use actions. Unknown control identifiers are marked invalid and reduce to a no-op at execution time.

## 12 Prompt Templates and Game Prompt Blocks

The runtime assembles the final model prompt from four pieces into a shared template: a game-level rules block, a role-and-controls block, a task-specific instruction block, and a model-specific output-format block.

### 12.1 Prompt Assembly: Shared Templates

Prompt assembly is driven by the prompt templates.
The stock templates for generalist agents and computer-use agents share a fixed section order:

1. 1.

   # Game Rules
2. 2.

   # Role and Controls
3. 3.

   # Task Instruction
4. 4.

   # Output Format

For computer-use agents, the role block combines the role description with an explicit textual control specification.
For generalist agents, the role block combines the role description with an automatically rendered semantic action list.
This list is built directly from the registry semantic\_controls entries and therefore stays synchronized with the executable action space.

#### 12.1.1 Generalist Agent Template

Below is the prompt template for generalist agents.

[⬇](data:text/plain;base64,WW91IGFyZSBhbiBleHBlcnQgZ2FtZSBhZ2VudCBzcGVjaWFsaXplZCBpbiBwbGF5aW5nIHZpZGVvIGdhbWVzLiBZb3VyIGdvYWwgaXMgdG8gcGxheSB0aGUgZ2FtZSBhbmQgYWNoaWV2ZSB0aGUgdGFzayBnb2FsLgpPYnNlcnZlIHRoZSBjdXJyZW50IGdhbWUgc2NyZWVuIHRvIGlkZW50aWZ5IHlvdXIgY2hhcmFjdGVyIGFuZCBrZXkgb2JqZWN0cy4gWW91ciBhY3Rpb24gbXVzdCBmb2xsb3cgdGhlIGdhbWUgcnVsZXMgYW5kIHRoZSBpbnN0cnVjdGlvbnMgb2YgdGhlIGN1cnJlbnQgdGFzay4KRXhlY3V0ZSB0aGUgYWN0aW9ucyBmcmFtZS1ieS1mcmFtZS4KWW91IGRvIE5PVCBoYXZlIGRpcmVjdCBhY2Nlc3MgdG8ga2V5Ym9hcmQgb3IgbW91c2UgYWN0aW9ucy4gWW91IG11c3QgYWN0IHRocm91Z2ggdGhlIHJlZ2lzdGVyZWQgc2VtYW50aWMgY29udHJvbCBsaXN0IG9ubHkuCgp7JSBpZiBnYW1lX3J1bGVzX2Jsb2NrICV9CiMgR2FtZSBSdWxlcwp7eyBnYW1lX3J1bGVzX2Jsb2NrIH19CnslIGVuZGlmICV9Cgp7JSBpZiByb2xlX2NvbnRyb2xfYmxvY2tfc2VtYW50aWMgJX0KIyBSb2xlIGFuZCBDb250cm9scwp7eyByb2xlX2NvbnRyb2xfYmxvY2tfc2VtYW50aWMgfX0KeyUgZW5kaWYgJX0KCnslIGlmIHRhc2tfaW5zdHJ1Y3Rpb25fYmxvY2sgJX0KIyBUYXNrIEluc3RydWN0aW9uCnt7IHRhc2tfaW5zdHJ1Y3Rpb25fYmxvY2sgfX0KeyUgZW5kaWYgJX0KCnslIGlmIG1vZGVsX291dHB1dF9mb3JtYXRfYmxvY2sgJX0KIyBPdXRwdXQgRm9ybWF0Cnt7IG1vZGVsX291dHB1dF9mb3JtYXRfYmxvY2sgfX0KeyUgZW5kaWYgJX0=)

You are an expert game agent specialized in playing video games. Your goal is to play the game and achieve the task goal.

Observe the current game screen to identify your character and key objects. Your action must follow the game rules and the instructions of the current task.

Execute the actions frame-by-frame.

You do NOT have direct access to keyboard or mouse actions. You must act through the registered semantic control list only.

{% if game\_rules\_block %}

# Game Rules

{{ game\_rules\_block }}

{% endif %}

{% if role\_control\_block\_semantic %}

# Role and Controls

{{ role\_control\_block\_semantic }}

{% endif %}

{% if task\_instruction\_block %}

# Task Instruction

{{ task\_instruction\_block }}

{% endif %}

{% if model\_output\_format\_block %}

# Output Format

{{ model\_output\_format\_block }}

{% endif %}

#### 12.1.2 Computer-Use Agent Template

Below is the prompt template for computer-use agents.

[⬇](data:text/plain;base64,WW91IGFyZSBhbiBleHBlcnQgZ2FtZSBhZ2VudCBzcGVjaWFsaXplZCBpbiBwbGF5aW5nIHZpZGVvIGdhbWVzLiBZb3VyIGdvYWwgaXMgdG8gcGxheSB0aGUgZ2FtZSBhbmQgYWNoaWV2ZSB0aGUgdGFzayBnb2FsLgpPYnNlcnZlIHRoZSBjdXJyZW50IGdhbWUgc2NyZWVuIHRvIGlkZW50aWZ5IHlvdXIgY2hhcmFjdGVyIGFuZCBrZXkgb2JqZWN0cy4gWW91ciBhY3Rpb24gbXVzdCBmb2xsb3cgdGhlIGdhbWUgcnVsZXMgYW5kIHRoZSBpbnN0cnVjdGlvbnMgb2YgdGhlIGN1cnJlbnQgdGFzay4KRXhlY3V0ZSB0aGUgYWN0aW9ucyBmcmFtZS1ieS1mcmFtZS4KCnslIGlmIGdhbWVfcnVsZXNfYmxvY2sgJX0KIyBHYW1lIFJ1bGVzCnt7IGdhbWVfcnVsZXNfYmxvY2sgfX0KeyUgZW5kaWYgJX0KCnslIGlmIHJvbGVfY29udHJvbF9ibG9ja19jb21wdXRlcl91c2UgJX0KIyBSb2xlIGFuZCBDb250cm9scwp7eyByb2xlX2NvbnRyb2xfYmxvY2tfY29tcHV0ZXJfdXNlIH19CnslIGVuZGlmICV9Cgp7JSBpZiB0YXNrX2luc3RydWN0aW9uX2Jsb2NrICV9CiMgVGFzayBJbnN0cnVjdGlvbgp7eyB0YXNrX2luc3RydWN0aW9uX2Jsb2NrIH19CnslIGVuZGlmICV9Cgp7JSBpZiBtb2RlbF9vdXRwdXRfZm9ybWF0X2Jsb2NrICV9CiMgT3V0cHV0IEZvcm1hdAp7eyBtb2RlbF9vdXRwdXRfZm9ybWF0X2Jsb2NrIH19CnslIGVuZGlmICV9)

You are an expert game agent specialized in playing video games. Your goal is to play the game and achieve the task goal.

Observe the current game screen to identify your character and key objects. Your action must follow the game rules and the instructions of the current task.

Execute the actions frame-by-frame.

{% if game\_rules\_block %}

# Game Rules

{{ game\_rules\_block }}

{% endif %}

{% if role\_control\_block\_computer\_use %}

# Role and Controls

{{ role\_control\_block\_computer\_use }}

{% endif %}

{% if task\_instruction\_block %}

# Task Instruction

{{ task\_instruction\_block }}

{% endif %}

{% if model\_output\_format\_block %}

# Output Format

{{ model\_output\_format\_block }}

{% endif %}

### 12.2 Per-Game Prompt Library

For each benchmark game below, we include the exact game-rules block together with the role prompt blocks loaded from the registry.
For each role, we include the shared role prompt text, the computer-use controls prompt text, and the semantic action list rendered for generalist agents from the registered semantic\_controls entries.
We also list the five benchmark task prompts for that game.

##### 1-2048 (2048).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIDIwNDgsIGEgc2xpZGluZyB0aWxlIHB1enpsZSBnYW1lLgoKR2FtZSBPYmplY3RpdmUuCi0gQ29tYmluZSBtYXRjaGluZyB0aWxlcyB0byBjcmVhdGUgaGlnaGVyIHZhbHVlcy4KR2FtZSBSdWxlcy4KLSBBbGwgdGlsZXMgc2xpZGUgaW4gdGhlIGRpcmVjdGlvbiB5b3UgcHJlc3MuCi0gV2hlbiB0d28gdGlsZXMgd2l0aCB0aGUgc2FtZSBudW1iZXIgY29sbGlkZSwgdGhleSBtZXJnZSBpbnRvIG9uZSB0aWxlIHdpdGggZG91YmxlZCB2YWx1ZS4KLSBBZnRlciBlYWNoIHZhbGlkIG1vdmUgKGFueSB0aWxlIGlzIG1vdmVkKSwgYSBuZXcgdGlsZSBvZiAyIG9yIDQgYXBwZWFycyBpbiBhIHJhbmRvbSBlbXB0eSBjZWxsLgotIEdhbWUgZW5kcyB3aGVuIG5vIG1vcmUgbW92ZXMgYXJlIHBvc3NpYmxlIChib2FyZCBpcyBmdWxsIGFuZCBubyBtZXJnZXMgYXZhaWxhYmxlKS4=)

You are playing 2048, a sliding tile puzzle game.

Game Objective.

- Combine matching tiles to create higher values.

Game Rules.

- All tiles slide in the direction you press.

- When two tiles with the same number collide, they merge into one tile with doubled value.

- After each valid move (any tile is moved), a new tile of 2 or 4 appears in a random empty cell.

- Game ends when no more moves are possible (board is full and no merges available).

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIDIwNDggYm9hcmQuIENob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXAgdG8gc2xpZGUgdGlsZXMu)

You control the 2048 board. Choose exactly one action per step to slide tiles.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBEbyBub3RoaW5nLgotIEFycm93VXA6IFNsaWRlIGFsbCB0aWxlcyB1cAotIEFycm93RG93bjogU2xpZGUgYWxsIHRpbGVzIGRvd24KLSBBcnJvd0xlZnQ6IFNsaWRlIGFsbCB0aWxlcyBsZWZ0Ci0gQXJyb3dSaWdodDogU2xpZGUgYWxsIHRpbGVzIHJpZ2h0)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Do nothing.

- ArrowUp: Slide all tiles up

- ArrowDown: Slide all tiles down

- ArrowLeft: Slide all tiles left

- ArrowRight: Slide all tiles right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcuCi0gbW92ZV91cDogU2xpZGUgYWxsIHRpbGVzIHVwLgotIG1vdmVfZG93bjogU2xpZGUgYWxsIHRpbGVzIGRvd24uCi0gbW92ZV9sZWZ0OiBTbGlkZSBhbGwgdGlsZXMgbGVmdC4KLSBtb3ZlX3JpZ2h0OiBTbGlkZSBhbGwgdGlsZXMgcmlnaHQu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing.

- move\_up: Slide all tiles up.

- move\_down: Slide all tiles down.

- move\_left: Slide all tiles left.

- move\_right: Slide all tiles right.

##### 2-another-gentlemans-adventure (Another Gentleman’s Adventure).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEFub3RoZXIgR2VudGxlbWFuJ3MgQWR2ZW50dXJlLCBhIHBsYXRmb3JtZXIgZ2FtZS4KCkdhbWUgT2JqZWN0aXZlLgotIE5hdmlnYXRlIHRocm91Z2ggbGV2ZWxzLCBhdm9pZGluZyBvYnN0YWNsZXMgYW5kIGVuZW1pZXMgdG8gZ2V0IGNvaW5zLgpHYW1lIFJ1bGVzLgotIE1vdmUgbGVmdCBhbmQgcmlnaHQgdG8gbmF2aWdhdGUgcGxhdGZvcm1zLgotIEp1bXAgKGxlZnQgb3IgcmlnaHQpIHRvIGF2b2lkIG9ic3RhY2xlcyBhbmQgcmVhY2ggaGlnaGVyIHBsYXRmb3Jtcy4KLSBKdW1wIGZyb20gYmVsb3cgdG8gaGl0IHRoZSBHb2xkZW4gUXVlc3Rpb24gQmxvY2tzIGFuZCByZXZlYWwgaXRlbXMuCi0gSnVtcGluZyBvbiBlbmVtaWVzIGtpbGxzIHRoZW0u)

You are playing Another Gentleman’s Adventure, a platformer game.

Game Objective.

- Navigate through levels, avoiding obstacles and enemies to get coins.

Game Rules.

- Move left and right to navigate platforms.

- Jump (left or right) to avoid obstacles and reach higher platforms.

- Jump from below to hit the Golden Question Blocks and reveal items.

- Jumping on enemies kills them.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGdlbnRsZW1hbiBjaGFyYWN0ZXIu)

You control the gentleman character.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBTdGF5IHN0aWxsLgotIEFycm93IExlZnQvUmlnaHQ6IE1vdmUgaG9yaXpvbnRhbGx5Ci0gQXJyb3cgVXA6IEp1bXAKLSBBcnJvdyBMZWZ0L1JpZ2h0ICsgQXJyb3cgVXAgKGtleSBjb21iaW5hdGlvbik6IEp1bXAgd2hpbGUgbW92aW5nIGxlZnQvcmlnaHRz)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Stay still.

- Arrow Left/Right: Move horizontally

- Arrow Up: Jump

- Arrow Left/Right + Arrow Up (key combination): Jump while moving left/rights

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFN0YXkgc3RpbGwgYnJpZWZseS4KLSBtb3ZlX2xlZnQ6IFdhbGsgbGVmdC4KLSBtb3ZlX3JpZ2h0OiBXYWxrIHJpZ2h0LgotIGp1bXA6IEp1bXAgdmVydGljYWxseS4KLSBqdW1wX2xlZnQ6IEp1bXAgd2hpbGUgbW92aW5nIGxlZnQuCi0ganVtcF9yaWdodDogSnVtcCB3aGlsZSBtb3ZpbmcgcmlnaHQu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Stay still briefly.

- move\_left: Walk left.

- move\_right: Walk right.

- jump: Jump vertically.

- jump\_left: Jump while moving left.

- jump\_right: Jump while moving right.

##### 3-astray (Astray).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEFzdHJheSwgYSBtYXplIG5hdmlnYXRpb24gZ2FtZS4KCkdhbWUgT2JqZWN0aXZlLgotIE5hdmlnYXRlIHRoZSBiYWxsIHRocm91Z2ggdGhlIG1hemUgdG8gcmVhY2ggdGhlIGV4aXQuCkdhbWUgUnVsZXMuCi0gTmF2aWdhdGUgdGhyb3VnaCB0aGUgbWF6ZSBjYXJlZnVsbHkgdG8gZmluZCB0aGUgcGF0aCB0byB0aGUgZXhpdC4KLSBUaGUgZXhpdCBpcyB0eXBpY2FsbHkgYXQgdGhlIHJpZ2h0LXRvcCBmYXIgY29ybmVyIG9mIHRoZSBtYXplLg==)

You are playing Astray, a maze navigation game.

Game Objective.

- Navigate the ball through the maze to reach the exit.

Game Rules.

- Navigate through the maze carefully to find the path to the exit.

- The exit is typically at the right-top far corner of the maze.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGJhbGwgaW4gdGhlIG1hemUuIFVzZSBhcnJvdyBrZXlzIHRvIG5hdmlnYXRlIHRvIHRoZSBleGl0Lg==)

You control the ball in the maze. Use arrow keys to navigate to the exit.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBXYWl0IGJyaWVmbHkgd2l0aG91dCBtb3ZpbmcKLSBBcnJvd1VwOiBNb3ZlIHRoZSBiYWxsIHVwCi0gQXJyb3dEb3duOiBNb3ZlIHRoZSBiYWxsIGRvd24KLSBBcnJvd0xlZnQ6IE1vdmUgdGhlIGJhbGwgbGVmdAotIEFycm93UmlnaHQ6IE1vdmUgdGhlIGJhbGwgcmlnaHQ=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Wait briefly without moving

- ArrowUp: Move the ball up

- ArrowDown: Move the ball down

- ArrowLeft: Move the ball left

- ArrowRight: Move the ball right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFdhaXQgYnJpZWZseSB3aXRob3V0IG1vdmluZy4KLSBtb3ZlX2xlZnQ6IE1vdmUgdGhlIGJhbGwgbGVmdC4KLSBtb3ZlX3JpZ2h0OiBNb3ZlIHRoZSBiYWxsIHJpZ2h0LgotIG1vdmVfdXA6IE1vdmUgdGhlIGJhbGwgdXAuCi0gbW92ZV9kb3duOiBNb3ZlIHRoZSBiYWxsIGRvd24u)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Wait briefly without moving.

- move\_left: Move the ball left.

- move\_right: Move the ball right.

- move\_up: Move the ball up.

- move\_down: Move the ball down.

##### 4-boxel-rebound (Boxel Rebound).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEJveGVsIFJlYm91bmQsIGEgcHJlY2lzaW9uIHBsYXRmb3JtZXIuCgpHYW1lIE9iamVjdGl2ZS4KLSBUaW1lIHlvdXIganVtcHMgdG8gbmF2aWdhdGUgdGhyb3VnaCBlYWNoIGxldmVsIHRvIHJlYWNoIHRoZSBlbmQgd2l0aG91dCBkeWluZy4KLSBZb3VyIGNoYXJhY3RlciBhdXRvbWF0aWNhbGx5IG1vdmVzIGZvcndhcmQgY29udGludW91c2x5LgpHYW1lIFJ1bGVzLgotIFlvdSBjYW4gb25seSBqdW1wIC0gbm8gbGVmdC9yaWdodCBtb3ZlbWVudCBjb250cm9sLgotIEF2b2lkIHNwaWtlcyBhbmQgZmFsbGluZyBpbnRvIHBpdHMu)

You are playing Boxel Rebound, a precision platformer.

Game Objective.

- Time your jumps to navigate through each level to reach the end without dying.

- Your character automatically moves forward continuously.

Game Rules.

- You can only jump - no left/right movement control.

- Avoid spikes and falling into pits.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGJveGVsIGNoYXJhY3Rlci4gVGltZSB5b3VyIGp1bXBzIHRvIG5hdmlnYXRlIHRocm91Z2ggdGhlIGxldmVsLg==)

You control the boxel character. Time your jumps to navigate through the level.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBEbyBub3RoaW5nIHRvIGNvbnRpbnVlIG1vdmVtZW50LgotIFNwYWNlIG9yIEFycm93VXA6IEp1bXA=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Do nothing to continue movement.

- Space or ArrowUp: Jump

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcgdG8gY29udGludWUgbW92ZW1lbnQuCi0ganVtcDogSnVtcCB0byBhdm9pZCBvYnN0YWNsZXMgb3IgY3Jvc3MgZ2Fwcy4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing to continue movement.

- jump: Jump to avoid obstacles or cross gaps.

##### 5-breakout (Breakout).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEJyZWFrb3V0LCBhIGNsYXNzaWMgYnJpY2stYnJlYWtpbmcgZ2FtZS4KCkdhbWUgT2JqZWN0aXZlLgotIEJyZWFrIGFsbCB0aGUgYnJpY2tzIHRvIGNvbXBsZXRlIGVhY2ggbGV2ZWwuIEVhY2ggYnJpY2sgYnJva2VuIGFkZHMgdG8geW91ciBzY29yZS4KR2FtZSBSdWxlcy4KLSBVc2UgdGhlIHBhZGRsZSB0byBib3VuY2UgdGhlIGJhbGwgdXB3YXJkLgotIEJyZWFrIGJyaWNrcyBieSBoaXR0aW5nIHRoZW0gd2l0aCB0aGUgYmFsbC4KLSBEb24ndCBsZXQgdGhlIGJhbGwgZmFsbCBwYXN0IHRoZSBwYWRkbGUu)

You are playing Breakout, a classic brick-breaking game.

Game Objective.

- Break all the bricks to complete each level. Each brick broken adds to your score.

Game Rules.

- Use the paddle to bounce the ball upward.

- Break bricks by hitting them with the ball.

- Don’t let the ball fall past the paddle.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHBhZGRsZS4gTW92ZSBsZWZ0IGFuZCByaWdodCB0byBrZWVwIHRoZSBiYWxsIGluIHBsYXkgYW5kIGJyZWFrIGJyaWNrcy4=)

You control the paddle. Move left and right to keep the ball in play and break bricks.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBTdGF5IHN0aWxsLgotIEFycm93IExlZnQvUmlnaHQ6IE1vdmUgcGFkZGxlCi0gU3BhY2U6IExhdW5jaCBiYWxsL1N0YXJ0IGdhbWU=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Stay still.

- Arrow Left/Right: Move paddle

- Space: Launch ball/Start game

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFN0YXkgc3RpbGwgYnJpZWZseS4KLSBtb3ZlX2xlZnQ6IE1vdmUgcGFkZGxlIGxlZnQuCi0gbW92ZV9yaWdodDogTW92ZSBwYWRkbGUgcmlnaHQu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Stay still briefly.

- move\_left: Move paddle left.

- move\_right: Move paddle right.

##### 6-captaincallisto (Captain Callisto).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIENhcHRhaW4gQ2FsbGlzdG8sIGEgcGxhdGZvcm0gYWR2ZW50dXJlLgoKR2FtZSBPYmplY3RpdmUuCi0gUmVhY2ggdGhlIGV4aXQgb2YgZWFjaCBhcmVhLgotIENvbGxlY3QgY29pbnMgYWxvbmcgdGhlIHdheS4KR2FtZSBSdWxlcy4KLSBNb3ZlIGxlZnQvcmlnaHQvdXAvZG93biBhbmQganVtcCBhY3Jvc3MgcGxhdGZvcm1zLgotIFVzZSB0aGUgamV0cGFjayB0byBmbHkgdXAgYWZ0ZXIgeW91IGNvbGxlY3RlZCB0aGUgZnVlbHMuCi0gS2lsbCB0aGUgZW5lbWllcyBieSBqdW1waW5nIG9uIHRoZW0uCi0gV2hlbiB5b3UgdG91Y2ggdGhlIGVuZW1pZXMgKG5vdCBmcm9tIGFib3ZlKSBvciBmYWxsaW5nLCB5b3Ugd2lsbCByZXNwYXduLgotIFlvdSBuZWVkIGEgbW92ZSB0byBzdGFydCB0aGUgbGV2ZWwgYWZ0ZXIgcmVzcGF3bmluZy4=)

You are playing Captain Callisto, a platform adventure.

Game Objective.

- Reach the exit of each area.

- Collect coins along the way.

Game Rules.

- Move left/right/up/down and jump across platforms.

- Use the jetpack to fly up after you collected the fuels.

- Kill the enemies by jumping on them.

- When you touch the enemies (not from above) or falling, you will respawn.

- You need a move to start the level after respawning.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgQ2FwdGFpbiBDYWxsaXN0by4gQ29udHJvbCB0aGUgcGxheWVyIHRvIG1vdmUsIGp1bXAsIGFuZCByZWFjaCB0aGUgZXhpdC4=)

You control Captain Callisto. Control the player to move, jump, and reach the exit.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBEbyBub3RoaW5nLgotIEFycm93TGVmdCAvIEFycm93UmlnaHQgb3IgQS9EOiBtb3ZlIGxlZnQvcmlnaHQKLSBBcnJvd1VwIC8gQXJyb3dEb3duIG9yIFcvUzogY2xpbWIgb3IgbW92ZSB2ZXJ0aWNhbGx5Ci0gU3BhY2U6IGp1bXAKLSBTaGlmdDogamV0cGFjawotIHI6IHJlc3RhcnQ=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Do nothing.

- ArrowLeft / ArrowRight or A/D: move left/right

- ArrowUp / ArrowDown or W/S: climb or move vertically

- Space: jump

- Shift: jetpack

- r: restart

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcuCi0gbW92ZV9sZWZ0OiBNb3ZlIGxlZnQuCi0gbW92ZV9yaWdodDogTW92ZSByaWdodC4KLSBtb3ZlX3VwOiBNb3ZlIHVwLgotIG1vdmVfZG93bjogTW92ZSBkb3duLgotIGp1bXA6IEp1bXAgb3ZlciBvYnN0YWNsZXMgb3IgZ2Fwcy4KLSBqZXRwYWNrOiBVc2UgdGhlIGpldHBhY2sgdG8gZmx5IHVwIChvbmx5IGlmIGF2YWlsYWJsZSkKLSByZXN0YXJ0OiBSZXN0YXJ0IHRoZSBsZXZlbC4gKFlvdSB3aWxsIG5lZWQgYSBtb3ZlIHRvIHN0YXJ0IHRoZSBsZXZlbCBhZnRlciByZXNwYXduaW5nKQ==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing.

- move\_left: Move left.

- move\_right: Move right.

- move\_up: Move up.

- move\_down: Move down.

- jump: Jump over obstacles or gaps.

- jetpack: Use the jetpack to fly up (only if available)

- restart: Restart the level. (You will need a move to start the level after respawning)

##### 7-chrome-dino (Chrome Dino).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIHRoZSBDaHJvbWUgRGlubyBydW5uZXIgZ2FtZS4gSnVtcCB0byBzdGFydCB0aGUgcnVuLgoKR2FtZSBPYmplY3RpdmUuCi0gU3Vydml2ZSBhcyBsb25nIGFzIHBvc3NpYmxlIHdoaWxlIHRoZSBkaW5vIHJ1bnMuCi0gQXZvaWQgb2JzdGFjbGVzIHRvIGtlZXAgdGhlIHJ1biBnb2luZyBhbmQgaW5jcmVhc2Ugc2NvcmUu)

You are playing the Chrome Dino runner game. Jump to start the run.

Game Objective.

- Survive as long as possible while the dino runs.

- Avoid obstacles to keep the run going and increase score.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGRpbm9zYXVyIHJ1bm5lci4gSnVtcCB0byBhdm9pZCBvYnN0YWNsZXMgYW5kIHN1cnZpdmUu)

You control the dinosaur runner. Jump to avoid obstacles and survive.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBEbyBub3RoaW5nIHRvIGtlZXAgdGhlIHJ1biBnb2luZy4KLSBTcGFjZS9BcnJvd1VwOiBKdW1wIG9yIHN0YXJ0IHRoZSBydW4=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Do nothing to keep the run going.

- Space/ArrowUp: Jump or start the run

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcgYnJpZWZseSB0byBrZWVwIHRoZSBydW4gZ29pbmcuCi0ganVtcDogSnVtcCBvdmVyIG9ic3RhY2xlcy4KLSBzdGFydDogU3RhcnQgb3IgcmVzdGFydCB0aGUgcnVuLg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing briefly to keep the run going.

- jump: Jump over obstacles.

- start: Start or restart the run.

##### 8-core-ball (Core Ball).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIENvcmUgQmFsbCwgYSBoaWdoLXNwZWVkIDJEIHRpbWluZy1hbmQtcHJlY2lzaW9uIGdhbWUuIFNob290IG51bWJlcmVkIGJhbGxzIGludG8gYSByb3RhdGluZyBjb3JlIGFuZCBhdHRhY2ggdGhlbSB0byBpdCB3aXRob3V0IGNvbGxpc2lvbnMuCgpHYW1lIE9iamVjdGl2ZS4KLSBBdHRhY2ggYWxsIGJhbGxzIGZvciB0aGUgY3VycmVudCBsZXZlbCB0byB0aGUgY29yZS4KLSBDb21wbGV0ZSB0aGUgbGV2ZWwgYmVmb3JlIHRoZSBxdWV1ZSBpcyBleGhhdXN0ZWQgYW5kIHRoZSBjb3JlIGJlY29tZXMgdG9vIGNyb3dkZWQuCi0gTGV2ZWxzIGdldCBmYXN0ZXIgYW5kIGRlbnNlciBhcyB5b3UgcHJvZ3Jlc3MuCkdhbWUgUnVsZXMuCi0gUHJlc3MgU3BhY2UgdG8gc2hvb3Qgb25lIGJhbGwgdG93YXJkIHRoZSBjZW50ZXIuCi0gQSBiYWxsIGNvbGxpc2lvbiB3aXRoIGFub3RoZXIgYmFsbCBmYWlscyB0aGUgcnVuIGltbWVkaWF0ZWx5Lg==)

You are playing Core Ball, a high-speed 2D timing-and-precision game. Shoot numbered balls into a rotating core and attach them to it without collisions.

Game Objective.

- Attach all balls for the current level to the core.

- Complete the level before the queue is exhausted and the core becomes too crowded.

- Levels get faster and denser as you progress.

Game Rules.

- Press Space to shoot one ball toward the center.

- A ball collision with another ball fails the run immediately.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgcHJlY2lzaW9uIGJhbGwgbGF1bmNoZXMgdG93YXJkIHRoZSBzcGlubmluZyBjb3JlLiBUaW1lIGVhY2ggc2hvdCBjYXJlZnVsbHkgYW5kIGtlZXAgdGhlIHBhdGggY2xlYXIu)

You control precision ball launches toward the spinning core. Time each shot carefully and keep the path clear.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBEbyBub3RoaW5nIHRvIHdhaXQgdGhlIGNvcmUgdG8gcm90YXRlCi0gU3BhY2U6IHNob290IG9uZSBiYWxs)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Do nothing to wait the core to rotate

- Space: shoot one ball

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkgYW5kIG9ic2VydmUgdGFyZ2V0IGFsaWdubWVudC4KLSBzaG9vdDogU2hvb3Qgb25lIGJhbGwgdG93YXJkIHRoZSBjb3JlLg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly and observe target alignment.

- shoot: Shoot one ball toward the core.

##### 9-cubefield (Cubefield).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEN1YmVmaWVsZCwgYSAzRCBlbmRsZXNzIHJ1bm5lciB3aGVyZSB5b3UgbmF2aWdhdGUgYSB0cmlhbmd1bGFyIHNoaXAgdGhyb3VnaCBhIGZpZWxkIG9mIGN1YmVzLgoKR2FtZSBPYmplY3RpdmUuCi0gU3Vydml2ZSBhcyBsb25nIGFzIHBvc3NpYmxlIGJ5IGF2b2lkaW5nIGN1YmUgb2JzdGFjbGVzLgpHYW1lIFJ1bGVzLgotIE1vdmUgbGVmdCBhbmQgcmlnaHQgdG8gZG9kZ2UgY3ViZXMuCi0gVGhlIHNoaXAgYXV0b21hdGljYWxseSBtb3ZlcyBmb3J3YXJkLgotIEhpdHRpbmcgYW55IGN1YmUgZW5kcyB0aGUgZ2FtZSBpbnN0YW50bHku)

You are playing Cubefield, a 3D endless runner where you navigate a triangular ship through a field of cubes.

Game Objective.

- Survive as long as possible by avoiding cube obstacles.

Game Rules.

- Move left and right to dodge cubes.

- The ship automatically moves forward.

- Hitting any cube ends the game instantly.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHRyaWFuZ3VsYXIgc2hpcC4gTW92ZSBsZWZ0IG9yIHJpZ2h0IHRvIG5hdmlnYXRlIHRocm91Z2ggdGhlIGN1YmUgZmllbGQu)

You control the triangular ship. Move left or right to navigate through the cube field.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBDb250aW51ZSBzdHJhaWdodC4KLSBBcnJvdyBMZWZ0OiBNb3ZlIGxlZnQKLSBBcnJvdyBSaWdodDogTW92ZSByaWdodA==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Continue straight.

- Arrow Left: Move left

- Arrow Right: Move right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IENvbnRpbnVlIHN0cmFpZ2h0LgotIG1vdmVfbGVmdDogTW92ZSBsZWZ0IHRvIGF2b2lkIGN1YmVzLgotIG1vdmVfcmlnaHQ6IE1vdmUgcmlnaHQgdG8gYXZvaWQgY3ViZXMu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Continue straight.

- move\_left: Move left to avoid cubes.

- move\_right: Move right to avoid cubes.

##### 10-doodle-jump (Doodle Jump).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIERvb2RsZSBKdW1wLCBhIHZlcnRpY2FsIHBsYXRmb3JtZXIuCgpHYW1lIE9iamVjdGl2ZS4KLSBLZWVwIGFzY2VuZGluZyBieSBsYW5kaW5nIG9uIGhpZ2hlciBwbGF0Zm9ybXMuCkdhbWUgUnVsZXMuCi0gR3JlZW4gcGxhdGZvcm1zOiBub3JtYWwgcGxhdGZvcm1zLgotIEJsdWUgbW92YWJsZSBwbGF0Zm9ybXM6IG1vdmluZyBsZWZ0IGFuZCByaWdodC4KLSBSZWQgYnJlYWthYmxlIHBsYXRmb3JtczogaWYgeW91IHN0ZXAgb24gaXQsIGl0IHdpbGwgYnJlYWsgYW5kIHlvdSB3aWxsIGZhbGwuCi0gV2hpdGUgdmFuaXNoYWJsZSBwbGF0Zm9ybXM6IGNhbiBzdGVwIG9uIGl0IG9uY2UsIGl0IHdpbGwgdmFuaXNoLgotIFRoZSBsZWZ0IGFuZCByaWdodCBzaWRlcyB3cmFwIGFyb3VuZCBlYWNoIG90aGVyLg==)

You are playing Doodle Jump, a vertical platformer.

Game Objective.

- Keep ascending by landing on higher platforms.

Game Rules.

- Green platforms: normal platforms.

- Blue movable platforms: moving left and right.

- Red breakable platforms: if you step on it, it will break and you will fall.

- White vanishable platforms: can step on it once, it will vanish.

- The left and right sides wrap around each other.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgRG9vZGxlLiBDb250cm9sIHRoZSBwbGF5ZXIgdG8gZHJpZnQgYW5kIGF2b2lkIGZhbGxpbmcu)

You control Doodle. Control the player to drift and avoid falling.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBEbyBub3RoaW5nIHRvIGNvbnRpbnVlIHZlcnRpY2FsIG1vdmVtZW50LgotIEFycm93TGVmdCAvIEFycm93UmlnaHQ6IG1vdmUgaG9yaXpvbnRhbGx5Lg==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Do nothing to continue vertical movement.

- ArrowLeft / ArrowRight: move horizontally.

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcgdG8gY29udGludWUgdmVydGljYWwgbW92ZW1lbnQuCi0gbW92ZV9sZWZ0OiBEcmlmdCBsZWZ0LgotIG1vdmVfcmlnaHQ6IERyaWZ0IHJpZ2h0Lg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing to continue vertical movement.

- move\_left: Drift left.

- move\_right: Drift right.

##### 11-edge-surf (Edge Surf).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEVkZ2UgU3VyZiwgYW4gZW5kbGVzcyBzdXJmaW5nIGdhbWUuIFlvdSBjb250cm9sIGEgc3VyZmVyIHJpZGluZyB3YXZlcyBhbmQgY29sbGVjdGluZyBpdGVtcy4KCkdhbWUgT2JqZWN0aXZlLgotIFN1cnZpdmUgYXMgbG9uZyBhcyBwb3NzaWJsZSB3aGlsZSBzdXJmaW5nLgotIEFjaGlldmUgdGhlIGhpZ2hlc3Qgc2NvcmUgYW5kIGRpc3RhbmNlIHdpdGggMyBsaXZlcy4KR2FtZSBSdWxlcy4KLSBZb3UgY2FuIG9ubHkgdHVybiBsZWZ0IG9yIHJpZ2h0LCBzbG93IGRvd24gb3IgYm9vc3QgdGhlIHN1cmZlci4KLSBIaXR0aW5nIG9ic3RhY2xlcyBjb3N0cyBsaXZlcy4KLSBDb2xsZWN0aW5nIGJvb3N0cyBnaXZlcyB0ZW1wb3Jhcnkgc3BlZWQsIGFuZCBzaGllbGRzIGdpdmVzIHRlbXBvcmFyeSBpbnZpbmNpYmlsaXR5Lg==)

You are playing Edge Surf, an endless surfing game. You control a surfer riding waves and collecting items.

Game Objective.

- Survive as long as possible while surfing.

- Achieve the highest score and distance with 3 lives.

Game Rules.

- You can only turn left or right, slow down or boost the surfer.

- Hitting obstacles costs lives.

- Collecting boosts gives temporary speed, and shields gives temporary invincibility.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHN1cmZlciBjaGFyYWN0ZXIuIFR1cm4gbGVmdCBhbmQgcmlnaHQgdG8gYXZvaWQgb2JzdGFjbGVzIGFuZCBjb2xsZWN0IGl0ZW1zLg==)

You control the surfer character. Turn left and right to avoid obstacles and collect items.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBDb250aW51ZSBzdXJmaW5nIGluIHRoZSBzYW1lIGRpcmVjdGlvbiB3aXRob3V0IGFjdGlvbi4KLSBBcnJvdyBMZWZ0OiBUdXJuIGxlZnQKLSBBcnJvdyBSaWdodDogVHVybiByaWdodAotIEFycm93IFVwOiBTbG93IGRvd24gdGhlIHN1cmZlcgotIEFycm93IERvd246IEJvb3N0IHRoZSBzdXJmZXIgKHJlcXVpcmVzIGEgYm9vc3QgaXRlbSk=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Continue surfing in the same direction without action.

- Arrow Left: Turn left

- Arrow Right: Turn right

- Arrow Up: Slow down the surfer

- Arrow Down: Boost the surfer (requires a boost item)

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IENvbnRpbnVlIHN1cmZpbmcgaW4gdGhlIHNhbWUgZGlyZWN0aW9uLgotIHR1cm5fbGVmdDogVHVybiBsZWZ0LgotIHR1cm5fcmlnaHQ6IFR1cm4gcmlnaHQuCi0gc2xvd19kb3duOiBTbG93IGRvd24gdGhlIHN1cmZlci4KLSBib29zdDogQm9vc3QgdGhlIHN1cmZlciAocmVxdWlyZXMgYSBib29zdCBpdGVtKS4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Continue surfing in the same direction.

- turn\_left: Turn left.

- turn\_right: Turn right.

- slow\_down: Slow down the surfer.

- boost: Boost the surfer (requires a boost item).

##### 12-fireboy-and-watergirl (Fireboy and Watergirl).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nICdGaXJlYm95IGFuZCBXYXRlcmdpcmwgaW4gVGhlIEZvcmVzdCBUZW1wbGUnLiBTb21lIHB1enpsZXMgcmVxdWlyZSBib3RoIGNoYXJhY3RlcnMgdG8gY29vcGVyYXRlIHRvIHNvbHZlLgoKR2FtZSBPYmplY3RpdmUuCi0gQm90aCBjaGFyYWN0ZXJzIG11c3QgcmVhY2ggdGhlaXIgcmVzcGVjdGl2ZSBleGl0IGRvb3JzIHRvIGNvbXBsZXRlIHRoZSBsZXZlbC4KLSBDb2xsZWN0IGFsbCBkaWFtb25kcyBmb3IgYSBoaWdoZXIgc2NvcmUuCkdhbWUgUnVsZXMuCi0gR3JlZW4gdG94aWMgbGlxdWlkOiBLaWxscyBCT1RIIGNoYXJhY3RlcnMKLSBSZWQgbGF2YSBwb29sczogS2lsbHMgV2F0ZXJnaXJsIG9ubHkKLSBCbHVlIHdhdGVyIHBvb2xzOiBLaWxscyBGaXJlYm95IG9ubHkKLSBCdXR0b25zIGFuZCBsZXZlcnMgY29udHJvbCBwbGF0Zm9ybXMgYW5kIGRvb3JzCi0gQm94ZXMgY2FuIGJlIHB1c2hlZCB0byByZWFjaCBoaWdoZXIgcGxhdGZvcm1z)

You are playing ’Fireboy and Watergirl in The Forest Temple’. Some puzzles require both characters to cooperate to solve.

Game Objective.

- Both characters must reach their respective exit doors to complete the level.

- Collect all diamonds for a higher score.

Game Rules.

- Green toxic liquid: Kills BOTH characters

- Red lava pools: Kills Watergirl only

- Blue water pools: Kills Fireboy only

- Buttons and levers control platforms and doors

- Boxes can be pushed to reach higher platforms

Role 0 (watergirl) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBBZ2VudCAwIGNvbnRyb2xsaW5nIHRoZSBXYXRlcmdpcmwgY2hhcmFjdGVyIChibHVlIGdpcmwpLgoKWU9VUiBPQkpFQ1RJVkVTOgoKLSBDb2xsZWN0IGJsdWUgZGlhbW9uZHMgKFdhdGVyZ2lybCdzIGdlbXMpCi0gUmVhY2ggdGhlIGJsdWUgZXhpdCBkb29yCi0gTkVWRVIgdG91Y2ggcmVkIGxhdmEgKGluc3RhbnQgZGVhdGgp)

You are Agent 0 controlling the Watergirl character (blue girl).

YOUR OBJECTIVES:

- Collect blue diamonds (Watergirl’s gems)

- Reach the blue exit door

- NEVER touch red lava (instant death)

Role 0 (watergirl) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXOiBKdW1wCi0gQTogTW92ZSBsZWZ0Ci0gRDogTW92ZSByaWdodAotIFcgKyBBOiBKdW1wIGxlZnQKLSBXICsgRDogSnVtcCByaWdodA==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- W: Jump

- A: Move left

- D: Move right

- W + A: Jump left

- W + D: Jump right

Role 0 (watergirl) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFN0YXkgc3RpbGwgYnJpZWZseS4KLSBtb3ZlX2xlZnQ6IFdhbGsgbGVmdCAoaG9sZCkuCi0gbW92ZV9yaWdodDogV2FsayByaWdodCAoaG9sZCkuCi0ganVtcF9sZWZ0OiBKdW1wIGRpYWdvbmFsbHkgbGVmdCAoanVtcCArIGxlZnQpLgotIGp1bXBfcmlnaHQ6IEp1bXAgZGlhZ29uYWxseSByaWdodCAoanVtcCArIHJpZ2h0KS4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Stay still briefly.

- move\_left: Walk left (hold).

- move\_right: Walk right (hold).

- jump\_left: Jump diagonally left (jump + left).

- jump\_right: Jump diagonally right (jump + right).

Role 1 (fireboy) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBBZ2VudCAxIGNvbnRyb2xsaW5nIHRoZSBGaXJlYm95IGNoYXJhY3RlciAocmVkIGJveSkuCgpZT1VSIE9CSkVDVElWRVM6CgotIENvbGxlY3QgcmVkIGRpYW1vbmRzIChGaXJlYm95J3MgZ2VtcykKLSBSZWFjaCB0aGUgcmVkIGV4aXQgZG9vcgotIE5FVkVSIHRvdWNoIGJsdWUgd2F0ZXIgKGluc3RhbnQgZGVhdGgp)

You are Agent 1 controlling the Fireboy character (red boy).

YOUR OBJECTIVES:

- Collect red diamonds (Fireboy’s gems)

- Reach the red exit door

- NEVER touch blue water (instant death)

Role 1 (fireboy) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VwOiBKdW1wCi0gQXJyb3dMZWZ0OiBNb3ZlIGxlZnQKLSBBcnJvd1JpZ2h0OiBNb3ZlIHJpZ2h0Ci0gQXJyb3dVcCArIEFycm93TGVmdDogSnVtcCBsZWZ0Ci0gQXJyb3dVcCArIEFycm93UmlnaHQ6IEp1bXAgcmlnaHQ=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUp: Jump

- ArrowLeft: Move left

- ArrowRight: Move right

- ArrowUp + ArrowLeft: Jump left

- ArrowUp + ArrowRight: Jump right

Role 1 (fireboy) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFN0YXkgc3RpbGwgYnJpZWZseS4KLSBtb3ZlX2xlZnQ6IFdhbGsgbGVmdCAoaG9sZCkuCi0gbW92ZV9yaWdodDogV2FsayByaWdodCAoaG9sZCkuCi0ganVtcF9sZWZ0OiBKdW1wIGRpYWdvbmFsbHkgbGVmdCAoanVtcCArIGxlZnQpLgotIGp1bXBfcmlnaHQ6IEp1bXAgZGlhZ29uYWxseSByaWdodCAoanVtcCArIHJpZ2h0KS4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Stay still briefly.

- move\_left: Walk left (hold).

- move\_right: Walk right (hold).

- jump\_left: Jump diagonally left (jump + left).

- jump\_right: Jump diagonally right (jump + right).

##### 13-flappy-bird (Flappy Bird).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEZsYXBweSBCaXJkLCBhIG9uZS1idXR0b24gZmx5aW5nIGdhbWUuCgpHYW1lIE9iamVjdGl2ZS4KLSBLZWVwIHRoZSBiaXJkIGZseWluZyBiZXR3ZWVuIHBpcGVzIGZvciBhcyBsb25nIGFzIHBvc3NpYmxlLgotIFBhc3MgcGlwZXMgdG8gaW5jcmVhc2UgeW91ciBzY29yZS4KR2FtZSBSdWxlcy4KLSBQcmVzcyBTcGFjZSB0byBmbGFwIHVwd2FyZDsgZ3Jhdml0eSBwdWxscyB5b3UgZG93bi4KLSBIaXR0aW5nIHBpcGVzIG9yIHRoZSBncm91bmQgZW5kcyB0aGUgcnVuLg==)

You are playing Flappy Bird, a one-button flying game.

Game Objective.

- Keep the bird flying between pipes for as long as possible.

- Pass pipes to increase your score.

Game Rules.

- Press Space to flap upward; gravity pulls you down.

- Hitting pipes or the ground ends the run.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGJpcmQuIFRhcCB0byBmbGFwIGFuZCBhdm9pZCB0aGUgcGlwZXMu)

You control the bird. Tap to flap and avoid the pipes.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBTcGFjZTogRmxhcCB1cHdhcmQKLSBXYWl0OiBEbyBub3RoaW5nIGJyaWVmbHkgdG8gbGV0IGdyYXZpdHkgcHVsbCBiaXJkIGRvd253YXJk)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Space: Flap upward

- Wait: Do nothing briefly to let gravity pull bird downward

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcgYnJpZWZseSB0byBsZXQgZ3Jhdml0eSBwdWxsIGJpcmQgZG93bndhcmQKLSBmbGFwOiBGbGFwIHVwd2FyZC4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing briefly to let gravity pull bird downward

- flap: Flap upward.

##### 14-geodash (GeoDash).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEdlb0Rhc2gsIGEgR2VvbWV0cnkgRGFzaC1zdHlsZSBhdXRvLXJ1bm5pbmcgcGxhdGZvcm1lci4KCkdhbWUgT2JqZWN0aXZlLgotIFN1cnZpdmUgZm9yIGFzIGxvbmcgYXMgcG9zc2libGUuCi0gSnVtcCBvdmVyIHNwaWtlcyBhbmQgaGF6YXJkcy4KR2FtZSBSdWxlcy4KLSBUaGUgY2hhcmFjdGVyIGF1dG8tcnVucyBjb250aW51b3VzbHkuCi0gSnVtcCB0aW1pbmcgaXMgdGhlIGNvcmUgbWVjaGFuaWMuCi0gQ3Jhc2hpbmcgaW50byBvYnN0YWNsZXMgZW5kcyB0aGUgcnVuLg==)

You are playing GeoDash, a Geometry Dash-style auto-running platformer.

Game Objective.

- Survive for as long as possible.

- Jump over spikes and hazards.

Game Rules.

- The character auto-runs continuously.

- Jump timing is the core mechanic.

- Crashing into obstacles ends the run.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHJ1bm5lci4gVGltZSBqdW1wcyB0byBhdm9pZCBzcGlrZXMgYW5kIHJ1biBhcyBsb25nIGFzIHBvc3NpYmxlLg==)

You control the runner. Time jumps to avoid spikes and run as long as possible.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBTcGFjZQ==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Space

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcgYnJpZWZseSB0byBrZWVwIHRoZSBkaXJlY3Rpb24uCi0ganVtcDogSnVtcC4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing briefly to keep the direction.

- jump: Jump.

##### 15-google-snake (Google Snake).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEdvb2dsZSBTbmFrZSwgdGhlIGNsYXNzaWMgc25ha2UgZ2FtZS4KCkdhbWUgT2JqZWN0aXZlLgotIEVhdCBhcHBsZXMgdG8gZ3JvdyBsb25nZXIgYW5kIGluY3JlYXNlIHNjb3JlLgotIEF2b2lkIGNyYXNoaW5nIGludG8gd2FsbHMgb3IgeW91ciBvd24gYm9keS4KR2FtZSBSdWxlcy4KLSBUaGUgc25ha2UgbW92ZXMgY29udGludW91c2x5IGluIHRoZSBjaG9zZW4gZGlyZWN0aW9uLgotIFlvdSBjYW4gdHVybiB1cCwgZG93biwgbGVmdCwgb3IgcmlnaHQuCi0gVGhlIGdhbWUgZW5kcyB3aGVuIHlvdSBoaXQgYSB3YWxsIG9yIHlvdXIgYm9keS4=)

You are playing Google Snake, the classic snake game.

Game Objective.

- Eat apples to grow longer and increase score.

- Avoid crashing into walls or your own body.

Game Rules.

- The snake moves continuously in the chosen direction.

- You can turn up, down, left, or right.

- The game ends when you hit a wall or your body.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHNuYWtlLiBVc2UgZGlyZWN0aW9uIGtleXMgdG8gZ3VpZGUgaXQgdG93YXJkIGFwcGxlcyBzYWZlbHku)

You control the snake. Use direction keys to guide it toward apples safely.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VQOiBUdXJuIHVwd2FyZAotIEFycm93RG93bjogVHVybiBkb3dud2FyZAotIEFycm93TGVmdDogVHVybiBsZWZ0Ci0gQXJyb3dSaWdodDogVHVybiByaWdodAotIFdhaXQ6IERvIG5vdGhpbmcgYnJpZWZseSB0byBrZWVwIHRoZSBkaXJlY3Rpb24=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUP: Turn upward

- ArrowDown: Turn downward

- ArrowLeft: Turn left

- ArrowRight: Turn right

- Wait: Do nothing briefly to keep the direction

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcgYnJpZWZseSB0byBrZWVwIHRoZSBkaXJlY3Rpb24uCi0gbW92ZV91cDogVHVybiB1cHdhcmQuCi0gbW92ZV9kb3duOiBUdXJuIGRvd253YXJkLgotIG1vdmVfbGVmdDogVHVybiBsZWZ0LgotIG1vdmVfcmlnaHQ6IFR1cm4gcmlnaHQu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing briefly to keep the direction.

- move\_up: Turn upward.

- move\_down: Turn downward.

- move\_left: Turn left.

- move\_right: Turn right.

##### 16-hextris (Hextris).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIEhleHRyaXMsIGEgZmFzdC1wYWNlZCBoZXhhZ29uLWJhc2VkIHB1enpsZSBnYW1lLgoKR2FtZSBPYmplY3RpdmUuCi0gTWF0Y2hpbmcgTWVjaGFuaXNtOiBHcm91cCAzIG9yIG1vcmUgYmxvY2tzIG9mIHRoZSBzYW1lIGNvbG9yIG9uIGFueSBvZiB0aGUgc2l4IHNpZGVzIHRvIGNsZWFyIHRoZW0gYW5kIGdldCBzY29yZXMuCi0gUHJldmVudCBibG9ja3MgZnJvbSBzdGFja2luZyBvdXRzaWRlIHRoZSBvdXRlciBib3VuZGFyeSBvZiB0aGUgY2VudHJhbCBoZXhhZ29uLgpHYW1lIFJ1bGVzLgotIFRoZSBnYW1lIHJ1bnMgY29udGludW91c2x5IGFuZCBibG9ja3MgZmFsbCBmcm9tIHRoZSBlZGdlcyBpbnRvIHRoZSBjZW50cmFsIGhleGFnb24uCi0gVGhlIHNwZWVkIG9mIHRoZSBmYWxsaW5nIGJsb2NrcyBpbmNyZWFzZXMgb3ZlciB0aW1lLgotIExlZnQvUmlnaHQgYXJyb3dzIHJvdGF0ZSB0aGUgaGV4YWdvbiBpbiBvcHBvc2l0ZSBkaXJlY3Rpb25zLgotIFByZXNzIERvd24gdG8gc3BlZWQgdXAgZmFsbGluZyBibG9jayBtb3Rpb24u)

You are playing Hextris, a fast-paced hexagon-based puzzle game.

Game Objective.

- Matching Mechanism: Group 3 or more blocks of the same color on any of the six sides to clear them and get scores.

- Prevent blocks from stacking outside the outer boundary of the central hexagon.

Game Rules.

- The game runs continuously and blocks fall from the edges into the central hexagon.

- The speed of the falling blocks increases over time.

- Left/Right arrows rotate the hexagon in opposite directions.

- Press Down to speed up falling block motion.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHJvdGF0aW5nIGhleGFnb24uIEtlZXAgdGhlIGJvYXJkIG1hbmFnZWFibGUgYnkgcm90YXRpbmcgcXVpY2tseSBhbmQgYmFsYW5jaW5nIGluY29taW5nIGJsb2Nrcy4=)

You control the rotating hexagon. Keep the board manageable by rotating quickly and balancing incoming blocks.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd0xlZnQ6IHJvdGF0ZSBoZXhhZ29uIGxlZnQKLSBBcnJvd1JpZ2h0OiByb3RhdGUgaGV4YWdvbiByaWdodAotIEFycm93RG93bjogYWNjZWxlcmF0ZSBmYWxsaW5nIGJsb2Nrcw==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowLeft: rotate hexagon left

- ArrowRight: rotate hexagon right

- ArrowDown: accelerate falling blocks

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IEJyaWVmbHkgd2FpdCB3aGlsZSB0aGUgYm9hcmQgZXZvbHZlcy4KLSByb3RhdGVfbGVmdDogUm90YXRlIHRoZSBoZXhhZ29uIGxlZnQgb25jZS4KLSByb3RhdGVfcmlnaHQ6IFJvdGF0ZSB0aGUgaGV4YWdvbiByaWdodCBvbmNlLgotIGFjY2VsZXJhdGU6IFRlbXBvcmFyaWx5IHNwZWVkIHVwIGZhbGxpbmcgYmxvY2tzLg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Briefly wait while the board evolves.

- rotate\_left: Rotate the hexagon left once.

- rotate\_right: Rotate the hexagon right once.

- accelerate: Temporarily speed up falling blocks.

##### 17-mario-game (Mario Game).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFN1cGVyIE1hcmlvIEJyb3MuIENvbnRyb2wgTWFyaW8gdGhyb3VnaCBwbGF0Zm9ybWluZyBsZXZlbHMsIGNvbGxlY3RpbmcgY29pbnMgYW5kIGRlZmVhdGluZyBlbmVtaWVzLgoKR2FtZSBPYmplY3RpdmUuCi0gUmVhY2ggdGhlIGZsYWdwb2xlIGF0IHRoZSBlbmQgb2YgZWFjaCBsZXZlbC4KLSBDb2xsZWN0IGNvaW5zIGZyb20gcXVlc3Rpb24gYmxvY2tzIG9yIGtpbGwgZW5lbWllcyBmb3IgcG9pbnRzLgpHYW1lIFJ1bGVzLgotIFlvdSBoYXZlIDMgbGl2ZXMgYW5kIGxpbWl0ZWQgdGltZSBwZXIgbGV2ZWwuCi0gVG91Y2hpbmcgZW5lbWllcyBmcm9tIHRoZSBzaWRlIG9yIGJlbG93IGtpbGxzIE1hcmlvLiBKdW1wIG9uIGVuZW1pZXMgdG8ga2lsbCBlbmVtaWVzLgotIEp1bXBpbmcgdW5kZXJuZWF0aCBxdWVzdGlvbiBibG9ja3Mgd2lsbCByZXZlYWwgY29pbnMgb3IgcG93ZXItdXBzLgotIFBvd2VyLXVwczogTXVzaHJvb20gbWFrZSBNYXJpbyBncm93IGJpZy4=)

You are playing Super Mario Bros. Control Mario through platforming levels, collecting coins and defeating enemies.

Game Objective.

- Reach the flagpole at the end of each level.

- Collect coins from question blocks or kill enemies for points.

Game Rules.

- You have 3 lives and limited time per level.

- Touching enemies from the side or below kills Mario. Jump on enemies to kill enemies.

- Jumping underneath question blocks will reveal coins or power-ups.

- Power-ups: Mushroom make Mario grow big.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgTWFyaW8uIE5hdmlnYXRlIHRocm91Z2ggcGxhdGZvcm1pbmcgbGV2ZWxzIGJ5IHJ1bm5pbmcsIGp1bXBpbmcsIGFuZCBhdm9pZGluZyBoYXphcmRzLg==)

You control Mario. Navigate through platforming levels by running, jumping, and avoiding hazards.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd0xlZnQ6IE1vdmUgbGVmdAotIEFycm93UmlnaHQ6IE1vdmUgcmlnaHQKLSBBcnJvd1VwOiBKdW1wCi0gQXJyb3dEb3duOiBEdWNrL2Nyb3VjaCAod2hlbiBiaWcpCi0gQXJyb3dVcCArIEFycm93TGVmdC9BcnJvd1JpZ2h0OiBKdW1wIHdoaWxlIG1vdmluZyBsZWZ0L3JpZ2h0)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowLeft: Move left

- ArrowRight: Move right

- ArrowUp: Jump

- ArrowDown: Duck/crouch (when big)

- ArrowUp + ArrowLeft/ArrowRight: Jump while moving left/right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFN0YW5kIHN0aWxsIGFuZCB3YWl0LgotIG1vdmVfcmlnaHQ6IFdhbGsgcmlnaHQuCi0gbW92ZV9sZWZ0OiBXYWxrIGxlZnQuCi0ganVtcDogSnVtcCBzdHJhaWdodCB1cC4KLSBqdW1wX3JpZ2h0OiBKdW1wIHdoaWxlIG1vdmluZyByaWdodC4KLSBqdW1wX2xlZnQ6IEp1bXAgd2hpbGUgbW92aW5nIGxlZnQuCi0gZHVjazogRHVjay9jcm91Y2ggKHdoZW4gYmlnKS4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Stand still and wait.

- move\_right: Walk right.

- move\_left: Walk left.

- jump: Jump straight up.

- jump\_right: Jump while moving right.

- jump\_left: Jump while moving left.

- duck: Duck/crouch (when big).

##### 18-minecraft-clone-glm (Minecraft Clone).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIGEgTWluZWNyYWZ0LXN0eWxlIGZpcnN0LXBlcnNvbiBzYW5kYm94IHN1cnZpdmFsIGdhbWUuCgpHYW1lIE9iamVjdGl2ZS4KLSBHYXRoZXIgcmVzb3VyY2VzIGJ5IGJyZWFraW5nIGJsb2Nrcy4KLSBNb3ZlIGFyb3VuZCBhbmQgbWluZSBuZWFyYnkgYmxvY2tzIGVmZmljaWVudGx5LgpHYW1lIFJ1bGVzLgotIEEgc2hvcnQgbGVmdCBjbGljayBwbGFjZXMgdGhlIGN1cnJlbnRseSBzZWxlY3RlZCBibG9jay4KLSBIb2xkIHRoZSBsZWZ0IG1vdXNlIGJ1dHRvbiBvbiB0aGUgdGFyZ2V0ZWQgYmxvY2sgdG8gbWluZSBpdC4gSG9sZC1taW5pbmcgaXMgYWNjZWxlcmF0ZWQgaW4gYmVuY2htYXJrIG1vZGUuCi0gWW91IGNhbiBhbHNvIHBsYWNlIGJsb2NrcyB3aXRoIHRoZSByaWdodCBtb3VzZSBidXR0b24uCi0gTW92ZSBhcm91bmQgYW5kIGp1bXAgdG8gbmF2aWdhdGUgdGhlIHRlcnJhaW4uCi0gTG9vayBhcm91bmQgdG8gYWltIGF0IGRpZmZlcmVudCBibG9ja3MuCi0gU2VsZWN0IGRpZmZlcmVudCBob3RiYXIgc2xvdHMgdG8gc3dpdGNoIGl0ZW1zLg==)

You are playing a Minecraft-style first-person sandbox survival game.

Game Objective.

- Gather resources by breaking blocks.

- Move around and mine nearby blocks efficiently.

Game Rules.

- A short left click places the currently selected block.

- Hold the left mouse button on the targeted block to mine it. Hold-mining is accelerated in benchmark mode.

- You can also place blocks with the right mouse button.

- Move around and jump to navigate the terrain.

- Look around to aim at different blocks.

- Select different hotbar slots to switch items.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHBsYXllciBjaGFyYWN0ZXIuIFByaW9yaXRpemUgZWZmaWNpZW50IG5lYXJieSByZXNvdXJjZSBjb2xsZWN0aW9uIGJ5IG1vdmluZyB0byBibG9ja3MgYW5kIG1pbmluZyB0aGVtLg==)

You control the player character. Prioritize efficient nearby resource collection by moving to blocks and mining them.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VwOiBtb3ZlIGZvcndhcmQKLSBBcnJvd0Rvd246IG1vdmUgYmFja3dhcmQKLSBBcnJvd0xlZnQ6IHN0cmFmZSBsZWZ0Ci0gQXJyb3dSaWdodDogc3RyYWZlIHJpZ2h0Ci0gU3BhY2U6IGp1bXAKLSBNb3VzZSBkcmFnOiBsb29rIGFyb3VuZCAvIHR1cm4gY2FtZXJhIChkcmFnIGZyb20gY2VudGVyIHRvd2FyZCBhIGRpcmVjdGlvbikKLSBMZWZ0IGNsaWNrOiBwbGFjZSB0aGUgc2VsZWN0ZWQgYmxvY2sKLSBMZWZ0IGNsaWNrIGFuZCBob2xkOiBtaW5lIHRoZSB0YXJnZXRlZCBibG9jawotIFJpZ2h0IG1vdXNlOiBwbGFjZSBzZWxlY3RlZCBibG9jawotIDEtOTogc2VsZWN0IGhvdGJhciBzbG90)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUp: move forward

- ArrowDown: move backward

- ArrowLeft: strafe left

- ArrowRight: strafe right

- Space: jump

- Mouse drag: look around / turn camera (drag from center toward a direction)

- Left click: place the selected block

- Left click and hold: mine the targeted block

- Right mouse: place selected block

- 1-9: select hotbar slot

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFdhaXQgYnJpZWZseS4KLSBtb3ZlX2ZvcndhcmQ6IE1vdmUgZm9yd2FyZCBicmllZmx5LgotIG1vdmVfYmFja3dhcmQ6IE1vdmUgYmFja3dhcmQgYnJpZWZseS4KLSBzdHJhZmVfbGVmdDogTW92ZSBsZWZ0IGJyaWVmbHkuCi0gc3RyYWZlX3JpZ2h0OiBNb3ZlIHJpZ2h0IGJyaWVmbHkuCi0ganVtcDogSnVtcCBvbmNlLgotIGxvb2tfbGVmdDogVHVybiBjYW1lcmEgbGVmdC4KLSBsb29rX3JpZ2h0OiBUdXJuIGNhbWVyYSByaWdodC4KLSBsb29rX3VwOiBUaWx0IGNhbWVyYSB1cC4KLSBsb29rX2Rvd246IFRpbHQgY2FtZXJhIGRvd24uCi0gbWluZV90YXJnZXQ6IEhvbGQgbGVmdCBjbGljayBhdCBjZW50ZXIgdG8gbWluZSB0aGUgdGFyZ2V0ZWQgYmxvY2suCi0gcGxhY2VfYmxvY2s6IFBsYWNlIHRoZSBzZWxlY3RlZCBibG9jayBhdCBjZW50ZXIuCi0gc2VsZWN0X3Nsb3RfMTogU2VsZWN0IGhvdGJhciBzbG90IDEuCi0gc2VsZWN0X3Nsb3RfMjogU2VsZWN0IGhvdGJhciBzbG90IDIuCi0gc2VsZWN0X3Nsb3RfMzogU2VsZWN0IGhvdGJhciBzbG90IDMu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Wait briefly.

- move\_forward: Move forward briefly.

- move\_backward: Move backward briefly.

- strafe\_left: Move left briefly.

- strafe\_right: Move right briefly.

- jump: Jump once.

- look\_left: Turn camera left.

- look\_right: Turn camera right.

- look\_up: Tilt camera up.

- look\_down: Tilt camera down.

- mine\_target: Hold left click at center to mine the targeted block.

- place\_block: Place the selected block at center.

- select\_slot\_1: Select hotbar slot 1.

- select\_slot\_2: Select hotbar slot 2.

- select\_slot\_3: Select hotbar slot 3.

##### 19-minesweeper (Minesweeper).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIE1pbmVzd2VlcGVyLCBhIGxvZ2ljIHB1enpsZS4KCkdhbWUgT2JqZWN0aXZlLgotIEZsYWcgYWxsIG1pbmVzLgpHYW1lIFJ1bGVzLgotIExlZnQgY2xpY2sgYSBjZWxsIHJldmVhbHMgaXQ7IHJpZ2h0IGNsaWNrIGZsYWdzIGEgbWluZS4KLSBBIG51bWJlciBzaG93cyBob3cgbWFueSBtaW5lcyBhcmUgYWRqYWNlbnQgdG8gdGhhdCBjZWxsLgotIENsaWNraW5nIGEgbWluZSBlbmRzIHRoZSBnYW1lLg==)

You are playing Minesweeper, a logic puzzle.

Game Objective.

- Flag all mines.

Game Rules.

- Left click a cell reveals it; right click flags a mine.

- A number shows how many mines are adjacent to that cell.

- Clicking a mine ends the game.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGJvYXJkIHRvIHJldmVhbCBzYWZlIGNlbGxzIGFuZCBhdm9pZCBtaW5lcy4=)

You control the board to reveal safe cells and avoid mines.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBNb3VzZSBsZWZ0IGNsaWNrOiBSZXZlYWwgYSBjZWxsCi0gTW91c2UgcmlnaHQgY2xpY2s6IEZsYWcgYSBtaW5l)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Mouse left click: Reveal a cell

- Mouse right click: Flag a mine

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkuCi0gcmV2ZWFsX2NlbGw6IFJldmVhbCBhIGNlbGwgYnkgaWQgKGNlbGw9ImExIi4uImk5IikuIChyZXF1aXJlZDogY2VsbCkKLSBmbGFnX2NlbGw6IEZsYWcgYSBjZWxsIGJ5IGlkIChjZWxsPSJhMSIuLiJpOSIpLiAocmVxdWlyZWQ6IGNlbGwp)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly.

- reveal\_cell: Reveal a cell by id (cell="a1".."i9"). (required: cell)

- flag\_cell: Flag a cell by id (cell="a1".."i9"). (required: cell)

##### 20-monkey-mart (Monkey Mart).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIE1vbmtleSBNYXJ0LCBhIHN0b3JlIG1hbmFnZW1lbnQgZ2FtZS4KCkdhbWUgT2JqZWN0aXZlLgotIFN0b2NrIHNoZWx2ZXMsIHNlcnZlIGN1c3RvbWVycywgYW5kIGVhcm4gbW9uZXkuCi0gRXhwYW5kIHRoZSBzdG9yZSBieSB1bmxvY2tpbmcgbmV3IHN0YXRpb25zIGFuZCB1cGdyYWRlcy4KR2FtZSBSdWxlcy4KLSBNb3ZlIHdpdGhpbiB0aGUgc3RvcmUgdG8gYXV0b21hdGljYWxseSBoYXJ2ZXN0LCBjYXJyeSwgYW5kIHJlc3RvY2sgaXRlbXMuCi0gU3RheSBuZWFyIHRoZSBiYW5hbmEgdHJlZSB0byBoYXJ2ZXN0IGJhbmFuYXMsIHRoZSBjb3JuIGZpZWxkIHRvIGhhcnZlc3QgY29ybiwgdGhlIGNvcnJlc3BvbmRpbmcgc2hlbHZlcyB0byBzdG9jayBpdGVtcywgYW5kIG1vc3QgaW1wb3J0YW50bHksIHRoZSBjb3VudGVyIHRvIHNlcnZlIGN1c3RvbWVycyBhbmQgY29sbGVjdCBncmVlbiBtb25leS4KLSBUaGUgbmVlZHMgb2YgY3VzdG9tZXJzIHdpbGwgcG9wIHVwIGF0IHRoZSB0b3Agb2YgdGhlbSwgYW5kIHlvdSBuZWVkIHRvIGhhdmUgdGhlIGl0ZW0gdGhleSB3YW50IHN0b2NrZWQgb24gdGhlIHNoZWx2ZXMgZm9yIHRoZW0gdG8gYnV5IGl0LgotIEN1c3RvbWVycyB0YWtlIGl0ZW1zIGFuZCBwYXkgYXQgdGhlIGNvdW50ZXIuCi0gU3RheSBhdCB0aGUgbGVmdCBvZiB0aGUgY291bnRlciB0byBzZXJ2ZSBjdXN0b21lcnMgYW5kIHRoZW4gY29sbGVjdCBncmVlbiBtb25leS4KLSBCYW5hbmEgdHJlZSBpcyBhdCB0aGUgYm90dG9tIG9mIHRoZSBzdG9yZSwgYmFuYW5hIHNoZWxmIGlzIGluIHRoZSBtaWRkbGUsIGNvcm4gZmllbGQgaXMgYXQgdGhlIGJvdHRvbSBsZWZ0LCBjb3JuIHNoZWxmIGlzIGF0IHRoZSB0b3Agb2YgdGhlIGNvcm4gZmllbGQsIGFuZCB0aGUgY291bnRlciBpcyBvbiB0aGUgbGVmdCBvZiB0aGUgYmFuYW5hIHNoZWxmLgotIFlvdSBoYXZlIG9uZSBhc3Npc3RhbnQgd2l0aCBvcmFuZ2UgaGF0IHRvIGNvbGxlY3QgYW5kIHJlc3RvY2sgY29ybnMsIGJ1dCB0aGV5IHdpbGwgb2NjYXNpb25hbGx5IGJlIGlkbGUsIHlvdSBuZWVkIHRvIHdha2UgdGhlbS4KLSBBc3Npc3RhbnQgd2lsbCBvbmx5IGhlbHAgY29sbGVjdCBhbmQgcmVzdG9jayBjb3Jucy4gVGhlcmVmb3JlLCB5b3UgbmVlZCB0byBjb2xsZWN0IGFuZCByZXN0b2NrIGJhbmFuYXMsIGFuZCBjb2xsZWN0IGdyZWVuIG1vbmV5IGJ5IHlvdXJzZWxmLgotIFlvdSBzaG91bGQgaW50ZXJsZWVhdmUgYmV0d2VlbiBoYXJ2ZXN0aW5nLCBzdG9ja2luZywgYW5kIHNlcnZpbmcgdG8ga2VlcCB0aGUgc3RvcmUgcnVubmluZyBlZmZpY2llbnRseS4gRm9yIGV4YW1wbGUsIGlmIHlvdSBrZWVwIGhhcnZlc3RpbmcgYW5kIHJlc3RvY2tpbmcsIGJ1dCBuZXZlciBzZXJ2ZSBjdXN0b21lcnMgYXQgdGhlIGNvdW50ZXIsIHlvdSB3b24ndCBjb2xsZWN0IGFueSBtb25leS4gT24gdGhlIG90aGVyIGhhbmQsIGlmIHlvdSBvbmx5IHN0YXkgYXQgdGhlIGNvdW50ZXIgdG8gc2VydmUgY3VzdG9tZXJzIHdpdGhvdXQgcmVzdG9ja2luZywgdGhlIHNoZWx2ZXMgd2lsbCBydW4gb3V0IG9mIHN0b2NrIGFuZCBjdXN0b21lcnMgd2lsbCB3YWl0IGZvciByZXN0b2NraW5nLgotIFVzZSBlYXJuaW5ncyB0byB1bmxvY2sgbmV3IGFyZWFzIGFuZCBhc3Npc3RhbnRzLg==)

You are playing Monkey Mart, a store management game.

Game Objective.

- Stock shelves, serve customers, and earn money.

- Expand the store by unlocking new stations and upgrades.

Game Rules.

- Move within the store to automatically harvest, carry, and restock items.

- Stay near the banana tree to harvest bananas, the corn field to harvest corn, the corresponding shelves to stock items, and most importantly, the counter to serve customers and collect green money.

- The needs of customers will pop up at the top of them, and you need to have the item they want stocked on the shelves for them to buy it.

- Customers take items and pay at the counter.

- Stay at the left of the counter to serve customers and then collect green money.

- Banana tree is at the bottom of the store, banana shelf is in the middle, corn field is at the bottom left, corn shelf is at the top of the corn field, and the counter is on the left of the banana shelf.

- You have one assistant with orange hat to collect and restock corns, but they will occasionally be idle, you need to wake them.

- Assistant will only help collect and restock corns. Therefore, you need to collect and restock bananas, and collect green money by yourself.

- You should interleeave between harvesting, stocking, and serving to keep the store running efficiently. For example, if you keep harvesting and restocking, but never serve customers at the counter, you won’t collect any money. On the other hand, if you only stay at the counter to serve customers without restocking, the shelves will run out of stock and customers will wait for restocking.

- Use earnings to unlock new areas and assistants.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIG1vbmtleSBjaGFyYWN0ZXIuIE1vdmUgYXJvdW5kIHRoZSBzdG9yZSB0byBzdG9jayBhbmQgbWFuYWdlIGl0ZW1zLg==)

You control the monkey character. Move around the store to stock and manage items.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VwOiBNb3ZlIHVwCi0gQXJyb3dEb3duOiBNb3ZlIGRvd24KLSBBcnJvd0xlZnQ6IE1vdmUgbGVmdAotIEFycm93UmlnaHQ6IE1vdmUgcmlnaHQKLSB3YWl0OiBTdGF5IHN0aWxsIHRvIHdhaXQgZm9yIGFzc2lzdGFudHMgYW5kIGN1c3RvbWVycw==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUp: Move up

- ArrowDown: Move down

- ArrowLeft: Move left

- ArrowRight: Move right

- wait: Stay still to wait for assistants and customers

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFN0YXkgc3RpbGwgdG8gd2FpdCBmb3IgYXNzaXN0YW50cyBhbmQgY3VzdG9tZXJzLgotIG1vdmVfdXA6IE1vdmUgdXAuCi0gbW92ZV9kb3duOiBNb3ZlIGRvd24uCi0gbW92ZV9sZWZ0OiBNb3ZlIGxlZnQuCi0gbW92ZV9yaWdodDogTW92ZSByaWdodC4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Stay still to wait for assistants and customers.

- move\_up: Move up.

- move\_down: Move down.

- move\_left: Move left.

- move\_right: Move right.

##### 21-ns-shaft (NS-Shaft).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIE5TLVNoYWZ0LCBhIGZhbGxpbmcgcGxhdGZvcm0gZ2FtZS4KCkdhbWUgT2JqZWN0aXZlLgotIERlc2NlbmQgYXMgZmFyIGFzIHBvc3NpYmxlIGJ5IGxhbmRpbmcgb24gcGxhdGZvcm1zLgotIEF2b2lkIGhhemFyZHMgd2hpbGUga2VlcGluZyB5b3VyIGNoYXJhY3RlciBhbGl2ZS4KR2FtZSBSdWxlcy4KLSBUaGUgY2hhcmFjdGVyIGZhbGxzIGRvd253YXJkIGF1dG9tYXRpY2FsbHkuCi0gTW92ZSBsZWZ0L3JpZ2h0IHRvIGxhbmQgb24gcGxhdGZvcm1zLgotIExpZmUgZGVjcmVhc2VzIHdoZW4geW91IHRvdWNoIHRoZSBwaWxsYXJkcwotIFlvdSB3aWxsIGRpZSBpZiB5b3UgZmFsbCBhbGwgdGhlIHdheSB0byB0aGUgYm90dG9tIG9yIHJ1biBvdXQgb2YgdGhlIGxpZmUu)

You are playing NS-Shaft, a falling platform game.

Game Objective.

- Descend as far as possible by landing on platforms.

- Avoid hazards while keeping your character alive.

Game Rules.

- The character falls downward automatically.

- Move left/right to land on platforms.

- Life decreases when you touch the pillards

- You will die if you fall all the way to the bottom or run out of the life.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGZhbGxpbmcgY2hhcmFjdGVyLiBNb3ZlIGxlZnQgYW5kIHJpZ2h0IHRvIGxhbmQgb24gcGxhdGZvcm1zIHNhZmVseS4=)

You control the falling character. Move left and right to land on platforms safely.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvdyBMZWZ0L1JpZ2h0OiBNb3ZlIGxlZnQvcmlnaHQ=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Arrow Left/Right: Move left/right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IERvIG5vdGhpbmcgYnJpZWZseS4KLSBtb3ZlX2xlZnQ6IE1vdmUgbGVmdC4KLSBtb3ZlX3JpZ2h0OiBNb3ZlIHJpZ2h0Lg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Do nothing briefly.

- move\_left: Move left.

- move\_right: Move right.

##### 22-ovo (OVO).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIE9WTywgYSBmYXN0IHBsYXRmb3JtZXIgd2l0aCB0cmFwcy4KCkdhbWUgT2JqZWN0aXZlLgotIFJlYWNoIHRoZSBleGl0IG9mIGVhY2ggbGV2ZWwuCi0gQ29sbGVjdCBjb2lucyB3aGlsZSBhdm9pZGluZyBoYXphcmRzLgpHYW1lIFJ1bGVzLgotIEF2b2lkIHRyYXBzIGFuZCBwaXRzLgotIFdoZW4geW91IGdvIG5leHQgdG8gdGhlIHdhbGwsIHlvdSBjYW4ganVtcCBoaWdoZXIuCi0gSnVtcCBvbiBwbGFjZSBhbmQgcHJlc3MgZG93biB0byBzbWFzaCB0aGUgZ3JvdW5kLg==)

You are playing OVO, a fast platformer with traps.

Game Objective.

- Reach the exit of each level.

- Collect coins while avoiding hazards.

Game Rules.

- Avoid traps and pits.

- When you go next to the wall, you can jump higher.

- Jump on place and press down to smash the ground.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGNoYXJhY3RlciBpbiBPVk8uIENvbnRyb2wgdGhlIHBsYXllciB0byBydW4gYW5kIGp1bXAgdGhyb3VnaCBsZXZlbHMu)

You control the character in OVO. Control the player to run and jump through levels.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd0xlZnQgLyBBcnJvd1JpZ2h0OiBtb3ZlIGxlZnQvcmlnaHQuCi0gQXJyb3dVcDoganVtcC4KLSBBcnJvd1VwICsgQXJyb3dSaWdodCAvIEFycm93TGVmdDoganVtcCB3aGlsZSBtb3ZpbmcgcmlnaHQgLyBsZWZ0LgotIEFycm93RG93bjogc21hc2ggdGhlIGdyb3VuZC4KLSBBcnJvd0Rvd24gKyBBcnJvd1JpZ2h0IC8gQXJyb3dMZWZ0OiBzbGlkZSByaWdodCAvIGxlZnQu)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowLeft / ArrowRight: move left/right.

- ArrowUp: jump.

- ArrowUp + ArrowRight / ArrowLeft: jump while moving right / left.

- ArrowDown: smash the ground.

- ArrowDown + ArrowRight / ArrowLeft: slide right / left.

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkuCi0gbW92ZV9sZWZ0OiBSdW4gbGVmdC4KLSBtb3ZlX3JpZ2h0OiBSdW4gcmlnaHQuCi0ganVtcDogSnVtcC4KLSBqdW1wX3JpZ2h0OiBKdW1wIHdoaWxlIG1vdmluZyByaWdodC4KLSBqdW1wX2xlZnQ6IEp1bXAgd2hpbGUgbW92aW5nIGxlZnQuCi0gc21hc2hfZ3JvdW5kOiBTbWFzaCB0aGUgZ3JvdW5kLgotIHNsaWRlX3JpZ2h0OiBTbGlkZSByaWdodC4KLSBzbGlkZV9sZWZ0OiBTbGlkZSBsZWZ0Lg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly.

- move\_left: Run left.

- move\_right: Run right.

- jump: Jump.

- jump\_right: Jump while moving right.

- jump\_left: Jump while moving left.

- smash\_ground: Smash the ground.

- slide\_right: Slide right.

- slide\_left: Slide left.

##### 23-pacman (Pac-Man).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFBhYy1NYW4sIGEgbWF6ZSBjaGFzZSBnYW1lLgoKR2FtZSBPYmplY3RpdmUuCi0gRWF0IGFsbCBwZWxsZXRzIGluIHRoZSBtYXplLgotIEF2b2lkIGdob3N0cywgb3IgZWF0IHRoZW0gYWZ0ZXIgZ3JhYmJpbmcgYSBwb3dlciBwZWxsZXQuClRJUFM6CgotIFVzZSBjb3JyaWRvcnMgdG8gYmFpdCBnaG9zdHMgaW50byBjb3JuZXJzLgotIFNhdmUgcG93ZXIgcGVsbGV0cyBmb3IgdHJpY2t5IHNlY3Rpb25zLg==)

You are playing Pac-Man, a maze chase game.

Game Objective.

- Eat all pellets in the maze.

- Avoid ghosts, or eat them after grabbing a power pellet.

TIPS:

- Use corridors to bait ghosts into corners.

- Save power pellets for tricky sections.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgUGFjLU1hbi4gQ29udHJvbCB0aGUgcGxheWVyIHRvIG1vdmUgdGhyb3VnaCB0aGUgbWF6ZS4=)

You control Pac-Man. Control the player to move through the maze.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VwOiBNb3ZlIHVwIHRocm91Z2ggdGhlIG1hemUKLSBBcnJvd0Rvd246IE1vdmUgZG93biB0aHJvdWdoIHRoZSBtYXplCi0gQXJyb3dMZWZ0OiBNb3ZlIGxlZnQgdGhyb3VnaCB0aGUgbWF6ZQotIEFycm93UmlnaHQ6IE1vdmUgcmlnaHQgdGhyb3VnaCB0aGUgbWF6ZQ==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUp: Move up through the maze

- ArrowDown: Move down through the maze

- ArrowLeft: Move left through the maze

- ArrowRight: Move right through the maze

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkuCi0gbW92ZV91cDogTW92ZSB1cC4KLSBtb3ZlX2Rvd246IE1vdmUgZG93bi4KLSBtb3ZlX2xlZnQ6IE1vdmUgbGVmdC4KLSBtb3ZlX3JpZ2h0OiBNb3ZlIHJpZ2h0Lg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly.

- move\_up: Move up.

- move\_down: Move down.

- move\_left: Move left.

- move\_right: Move right.

##### 24-restless-wing-syndrome (Restless Wing Syndrome).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFJlc3RsZXNzIFdpbmcgU3luZHJvbWUsIGEgcGxhdGZvcm1lciB3aXRoIGF1dG9tYXRpYyBmbGFwcy4KCkdhbWUgT2JqZWN0aXZlLgotIFJlYWNoIHRoZSBleGl0IChsb29rcyBsaWtlIGEgYnJlYWQpIG9mIGVhY2ggbGV2ZWwuCi0gQXZvaWQgc3Bpa2VzIGFuZCBoYXphcmRzLgpHYW1lIFJ1bGVzLgotIFRoZSBiaXJkIGZsYXBzIGF1dG9tYXRpY2FsbHkgb24gYSB0aW1lciAoZmxhcCBtZXRlciBhdCB0b3AgbGVmdCkuIFRoZSBmbGFwIG1ldGVyIHdpbGwgYXV0b21hdGljYWxseSBkZWNyZWFzZSwgb25lIGNlbGwgYXQgYSB0aW1lLiBXaGVuIGl0IGlzIGVtcHR5LCB0aGUgYmlyZCB3aWxsIGF1dG9tYXRpY2FsbHkganVtcCB1cCB0aGVuIHRoZSBtZXRlciB3aWxsIGJlIHJlY2hhcmdlZCB0byBmdWxsLiBZb3UgY2FuIG9ic2VydmUgdGhlIGZsYXAgbWV0ZXIgdG8gdGltZSB5b3VyIG1vdmVtZW50cy4KLSBZb3UgY2FuIG1vdmUgbGVmdCBvciByaWdodCB0byBzdGVlciBtaWQtYWlyLgotIEhvbGQgVXAgdG8gZ2xpZGUgKHNsb3cgZGVzY2VudCkgaW4gdGhlIGFpci4KLSBVc2UgVXArTGVmdCBvciBVcCtSaWdodCB0byBnbGlkZSBkaWFnb25hbGx5LgotIE1vc3Qgb2YgdGhlIHRpbWUgdGhlIG1vdmVtZW50cyBhcmUgYWNoaWV2ZWQgYnkgZ2xpZGluZyB3aXRoIGFwcHJvcHJpYXRlIGRpcmVjdGlvbi4=)

You are playing Restless Wing Syndrome, a platformer with automatic flaps.

Game Objective.

- Reach the exit (looks like a bread) of each level.

- Avoid spikes and hazards.

Game Rules.

- The bird flaps automatically on a timer (flap meter at top left). The flap meter will automatically decrease, one cell at a time. When it is empty, the bird will automatically jump up then the meter will be recharged to full. You can observe the flap meter to time your movements.

- You can move left or right to steer mid-air.

- Hold Up to glide (slow descent) in the air.

- Use Up+Left or Up+Right to glide diagonally.

- Most of the time the movements are achieved by gliding with appropriate direction.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGJpcmQuIFN0ZWVyIGxlZnQvcmlnaHQgdG8gbmF2aWdhdGUgcGxhdGZvcm1zIGFuZCBoYXphcmRzLiBIb2xkIFVwIHRvIGdsaWRlIChzbG93IGRlc2NlbnQpLiBVc2UgVXArTGVmdC9SaWdodCB0byBnbGlkZSBkaWFnb25hbGx5LiBZb3UgY2FuIHVzZSBnbGlkZSBhY3Rpb25zIGNvbnNlY3V0aXZlbHkgZm9yIHN1c3RhaW5lZCBzbG93IGRlc2NlbnQu)

You control the bird. Steer left/right to navigate platforms and hazards. Hold Up to glide (slow descent). Use Up+Left/Right to glide diagonally. You can use glide actions consecutively for sustained slow descent.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd0xlZnQgLyBBcnJvd1JpZ2h0OiBNb3ZlIGxlZnQvcmlnaHQKLSBBcnJvd1VwOiBIb2xkIHRvIGdsaWRlIChzbG93IGRlc2NlbnQsIHVzZXMgZmxhcCBtZXRlcikKLSBBcnJvd1VwICsgQXJyb3dMZWZ0IC8gQXJyb3dSaWdodDogR2xpZGUgd2hpbGUgbW92aW5nIGxlZnQvcmlnaHQ=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowLeft / ArrowRight: Move left/right

- ArrowUp: Hold to glide (slow descent, uses flap meter)

- ArrowUp + ArrowLeft / ArrowRight: Glide while moving left/right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFN0YXkgc3RpbGwgYnJpZWZseS4KLSBtb3ZlX2xlZnQ6IE1vdmUgbGVmdC4KLSBtb3ZlX3JpZ2h0OiBNb3ZlIHJpZ2h0LgotIGdsaWRlOiBIb2xkIHRvIHNsb3cgZGVzY2VudCB1c2luZyBmbGFwIG1ldGVyLgotIGdsaWRlX2xlZnQ6IEdsaWRlIHdoaWxlIG1vdmluZyBsZWZ0IChzbG93IGRlc2NlbnQgKyBsZWZ0KS4KLSBnbGlkZV9yaWdodDogR2xpZGUgd2hpbGUgbW92aW5nIHJpZ2h0IChzbG93IGRlc2NlbnQgKyByaWdodCku)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Stay still briefly.

- move\_left: Move left.

- move\_right: Move right.

- glide: Hold to slow descent using flap meter.

- glide\_left: Glide while moving left (slow descent + left).

- glide\_right: Glide while moving right (slow descent + right).

##### 25-rocket-league-2d (Rocket League 2D).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFJvY2tldCBMZWFndWUgMkQsIGEgc2lkZS12aWV3IGNhciBzb2NjZXIgZ2FtZS4KCkdhbWUgT2JqZWN0aXZlLgotIFNjb3JlIGdvYWxzIGJ5IGhpdHRpbmcgdGhlIGJhbGwgaW50byB0aGUgb3Bwb25lbnQncyBuZXQuCi0gUHJldmVudCB0aGUgb3Bwb25lbnQgZnJvbSBzY29yaW5nLgpHYW1lIFJ1bGVzLgotIERyaXZlIGxlZnQvcmlnaHQgdG8gcG9zaXRpb24geW91ciBjYXIuCi0gSnVtcCB0byBoaXQgdGhlIGJhbGwgaW4gdGhlIGFpci4KLSBCb29zdCBjYW4gaW5jcmVhc2Ugc3BlZWQgaWYgYXZhaWxhYmxlLg==)

You are playing Rocket League 2D, a side-view car soccer game.

Game Objective.

- Score goals by hitting the ball into the opponent’s net.

- Prevent the opponent from scoring.

Game Rules.

- Drive left/right to position your car.

- Jump to hit the ball in the air.

- Boost can increase speed if available.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGJsdWUgY2FyLiBEcml2ZSwganVtcCwgYW5kIGJvb3N0IHRvIGhpdCB0aGUgYmFsbCBhbmQgc2NvcmUgZ29hbHMu)

You control the blue car. Drive, jump, and boost to hit the ball and score goals.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBL0Q6IERyaXZlCi0gVzogSnVtcAotIFNwYWNlOiBCb29zdCBvciBzcGVlZCB1cCAoaWYgYXZhaWxhYmxlKQ==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- A/D: Drive

- W: Jump

- Space: Boost or speed up (if available)

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkuCi0gbW92ZV9sZWZ0OiBEcml2ZSBsZWZ0LgotIG1vdmVfcmlnaHQ6IERyaXZlIHJpZ2h0LgotIGp1bXA6IEp1bXAgdG8gaGl0IHRoZSBiYWxsLgotIGJvb3N0OiBVc2UgYm9vc3Qgb3Igc3BlZWQgdXAgaWYgc3VwcG9ydGVkLg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly.

- move\_left: Drive left.

- move\_right: Drive right.

- jump: Jump to hit the ball.

- boost: Use boost or speed up if supported.

##### 26-run-3 (Run 3).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFJ1biAzLCBhbiBlbmRsZXNzIHR1bm5lbCBydW5uZXIuCgpHYW1lIE9iamVjdGl2ZS4KLSBTdXJ2aXZlIGFzIGxvbmcgYXMgcG9zc2libGUgd2hpbGUgbmF2aWdhdGluZyBnYXBzLgpHYW1lIFJ1bGVzLgotIFN0cmFmZSBsZWZ0L3JpZ2h0IHRvIG5hdmlnYXRlIGdhcHMuCi0gSnVtcCB0byBjcm9zcyBnYXBzLg==)

You are playing Run 3, an endless tunnel runner.

Game Objective.

- Survive as long as possible while navigating gaps.

Game Rules.

- Strafe left/right to navigate gaps.

- Jump to cross gaps.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSB0aGUgcnVubmVyLiBDb250cm9sIHRoZSBwbGF5ZXIgdG8gc3RyYWZlIGFuZCBqdW1wIG92ZXIgZ2Fwcy4gWW91IHJ1biB0aHJvdWdoIHR1bm5lbHMgaW4gUnVuIDMu)

You are the runner. Control the player to strafe and jump over gaps. You run through tunnels in Run 3.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd0xlZnQgLyBBcnJvd1JpZ2h0OiBzdHJhZmUgbGVmdC9yaWdodC4KLSBBcnJvd1VwIG9yIFNwYWNlOiBqdW1wLg==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowLeft / ArrowRight: strafe left/right.

- ArrowUp or Space: jump.

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkuCi0gbW92ZV9sZWZ0OiBTdHJhZmUgbGVmdCBhbG9uZyB0aGUgdHVubmVsLgotIG1vdmVfcmlnaHQ6IFN0cmFmZSByaWdodCBhbG9uZyB0aGUgdHVubmVsLgotIGp1bXA6IEp1bXAgYWNyb3NzIGdhcHMu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly.

- move\_left: Strafe left along the tunnel.

- move\_right: Strafe right along the tunnel.

- jump: Jump across gaps.

##### 27-stack (Stack).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFN0YWNrLCBhIHRpbWluZy1iYXNlZCBibG9jayBzdGFja2luZyBnYW1lLgoKR2FtZSBPYmplY3RpdmUuCi0gRHJvcCBlYWNoIG1vdmluZyBibG9jayB0byBhbGlnbiB3aXRoIHRoZSBzdGFjay4KLSBCdWlsZCB0aGUgaGlnaGVzdCBzdGFjayBwb3NzaWJsZS4KR2FtZSBSdWxlcy4KLSBFYWNoIGJsb2NrIG1vdmVzIGJhY2sgYW5kIGZvcnRoIG92ZXIgdGhlIHRvd2VyLgotIFByZXNzIFNwYWNlIHRvIGRyb3AgdGhlIGJsb2NrLgotIEFueSBvdmVyaGFuZ2luZyBwYXJ0IGlzIGN1dCBvZmYuCi0gVGhlIGdhbWUgZW5kcyB3aGVuIHRoZXJlIGlzIG5vIG92ZXJsYXAu)

You are playing Stack, a timing-based block stacking game.

Game Objective.

- Drop each moving block to align with the stack.

- Build the highest stack possible.

Game Rules.

- Each block moves back and forth over the tower.

- Press Space to drop the block.

- Any overhanging part is cut off.

- The game ends when there is no overlap.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHN0YWNraW5nIGJsb2Nrcy4gWW91IGFyZSBzdGFja2luZyBibG9ja3MgYnkgdGltaW5nIGRyb3BzLg==)

You control the stacking blocks. You are stacking blocks by timing drops.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBXYWl0OiBEbyBub3RoaW5nIHRvIHdhaXQgdGhlIHN0YWNrIHRvIG1vdmUKLSBTcGFjZTogRHJvcCB0aGUgYmxvY2sgb25jZQ==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Wait: Do nothing to wait the stack to move

- Space: Drop the block once

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFdhaXQgYnJpZWZseS4KLSBkcm9wX2Jsb2NrOiBEcm9wIHRoZSBibG9jayB0byBwbGFjZSBpdC4=)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Wait briefly.

- drop\_block: Drop the block to place it.

##### 28-temple-run-2 (Temple Run 2).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFRlbXBsZSBSdW4gMiwgYW4gZW5kbGVzcyBydW5uZXIuCgpHYW1lIE9iamVjdGl2ZS4KLSBTdXJ2aXZlIGFzIGxvbmcgYXMgcG9zc2libGUgd2l0aG91dCBtaXNzaW5nIHR1cm5zIGFuZCBhdm9pZCBvYnN0YWNsZXMuCkdhbWUgUnVsZXMuCi0gUnVuIGFsb25nIHRoZSBwYXRocyBhbmQgYXZvaWQgb2JzdGFjbGVzLgotIEZhaWwgdG8gdHVybiwganVtcCwgb3Igc2xpZGUgYW5kIHlvdSB3aWxsIGRpZS4=)

You are playing Temple Run 2, an endless runner.

Game Objective.

- Survive as long as possible without missing turns and avoid obstacles.

Game Rules.

- Run along the paths and avoid obstacles.

- Fail to turn, jump, or slide and you will die.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSB0aGUgcnVubmVyLiBDb250cm9sIHRoZSBwbGF5ZXIgdG8gdHVybiwganVtcCwgYW5kIHNsaWRlIHRvIGF2b2lkIG9ic3RhY2xlcy4gWW91IHJ1biBpbiBUZW1wbGUgUnVuIDIu)

You are the runner. Control the player to turn, jump, and slide to avoid obstacles. You run in Temple Run 2.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBL0Q6IHN3aXRjaCBsYW5lcyBhbmQgdGFrZSB0dXJucy4KLSBXOiBqdW1wLgotIFM6IHNsaWRlLgotIFNwYWNlOiBzdGFydC9jb250aW51ZS4=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- A/D: switch lanes and take turns.

- W: jump.

- S: slide.

- Space: start/continue.

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkuCi0gc3RhcnQ6IFN0YXJ0IG9yIGNvbnRpbnVlIHRoZSBydW4uCi0gdHVybl9sZWZ0OiBTd2l0Y2ggbGVmdCBsYW5lcyBvciB0YWtlIGEgbGVmdCB0dXJuLgotIHR1cm5fcmlnaHQ6IFN3aXRjaCByaWdodCBsYW5lcyBvciB0YWtlIGEgcmlnaHQgdHVybi4KLSBqdW1wOiBKdW1wIG92ZXIgb2JzdGFjbGVzLgotIHNsaWRlOiBTbGlkZSB1bmRlciBvYnN0YWNsZXMu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly.

- start: Start or continue the run.

- turn\_left: Switch left lanes or take a left turn.

- turn\_right: Switch right lanes or take a right turn.

- jump: Jump over obstacles.

- slide: Slide under obstacles.

##### 29-tetris (Tetris).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFRldHJpcywgYSBmYWxsaW5nIGJsb2NrIHB1enpsZSBnYW1lLgoKR2FtZSBPYmplY3RpdmUuCi0gQ2xlYXIgbGluZXMgYnkgZmlsbGluZyB0aGVtIHdpdGggYmxvY2tzLgotIFByZXZlbnQgdGhlIHN0YWNrIGZyb20gcmVhY2hpbmcgdGhlIHRvcCBhbmQgZ2V0IHRoZSBoaWdoZXN0IHNjb3JlIHBvc3NpYmxlLgpHYW1lIFJ1bGVzLgotIFBpZWNlcyBmYWxsIGZyb20gdGhlIHRvcCBhbmQgY2FuIGJlIG1vdmVkIG9yIHJvdGF0ZWQuCi0gQ29tcGxldGVkIGhvcml6b250YWwgbGluZXMgY2xlYXIgYW5kIHNjb3JlIHBvaW50cy4KLSBUaGUgZ2FtZSBlbmRzIHdoZW4gbmV3IHBpZWNlcyBjYW4gbm8gbG9uZ2VyIHNwYXduIG9yIHRoZSBzdGFjayByZWFjaGVzIHRoZSB0b3Au)

You are playing Tetris, a falling block puzzle game.

Game Objective.

- Clear lines by filling them with blocks.

- Prevent the stack from reaching the top and get the highest score possible.

Game Rules.

- Pieces fall from the top and can be moved or rotated.

- Completed horizontal lines clear and score points.

- The game ends when new pieces can no longer spawn or the stack reaches the top.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGZhbGxpbmcgcGllY2VzLiBDb250cm9sIHRoZSBwbGF5ZXIgdG8gbW92ZSwgcm90YXRlLCBkcm9wLCBhbmQgc3dhcCBwaWVjZXMuIFlvdSBhcmUgcGxheWluZyBUZXRyaXMuIEtlZXAgdGhlIHN0YWNrIGxvdyBhbmQgY2xlYXIgbGluZXMgZWZmaWNpZW50bHku)

You control the falling pieces. Control the player to move, rotate, drop, and swap pieces. You are playing Tetris. Keep the stack low and clear lines efficiently.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd0xlZnQgLyBBcnJvd1JpZ2h0OiBtb3ZlCi0gQXJyb3dVcCBvciBYOiByb3RhdGUgY2xvY2t3aXNlCi0gWjogcm90YXRlIGNvdW50ZXItY2xvY2t3aXNlCi0gQXJyb3dEb3duOiBzb2Z0IGRyb3AKLSBTcGFjZTogaGFyZCBkcm9wCi0gU2hpZnQgb3IgQzogU3dhcCBwaWVjZQotIEVudGVyIG9yIGNsaWNrOiBzdGFydC9yZXRyeQ==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowLeft / ArrowRight: move

- ArrowUp or X: rotate clockwise

- Z: rotate counter-clockwise

- ArrowDown: soft drop

- Space: hard drop

- Shift or C: Swap piece

- Enter or click: start/retry

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFdhaXQgYnJpZWZseS4KLSBtb3ZlX2xlZnQ6IFNoaWZ0IHRoZSBwaWVjZSBsZWZ0LgotIG1vdmVfcmlnaHQ6IFNoaWZ0IHRoZSBwaWVjZSByaWdodC4KLSBzb2Z0X2Ryb3A6IFNvZnQgZHJvcCB0aGUgcGllY2UgZmFzdGVyLgotIHJvdGF0ZV9jdzogUm90YXRlIHRoZSBwaWVjZSBjbG9ja3dpc2UuCi0gcm90YXRlX2NjdzogUm90YXRlIHRoZSBwaWVjZSBjb3VudGVyLWNsb2Nrd2lzZS4KLSBoYXJkX2Ryb3A6IEhhcmQgZHJvcCB0aGUgcGllY2UuCi0gaG9sZF9waWVjZTogSG9sZCBvciBzd2FwIHRoZSBjdXJyZW50IHBpZWNlLg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Wait briefly.

- move\_left: Shift the piece left.

- move\_right: Shift the piece right.

- soft\_drop: Soft drop the piece faster.

- rotate\_cw: Rotate the piece clockwise.

- rotate\_ccw: Rotate the piece counter-clockwise.

- hard\_drop: Hard drop the piece.

- hold\_piece: Hold or swap the current piece.

##### 30-vex-3 (Vex 3).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFZleCAzLCBhIHByZWNpc2lvbiBwbGF0Zm9ybWVyIHdpdGggdHJhcHMuCgpHYW1lIE9iamVjdGl2ZS4KLSBSZWFjaCB0aGUgY2hlY2twb2ludHMgYW5kIHRoZW4gdGhlIGV4aXQgb2YgZWFjaCBsZXZlbC4KLSBBdm9pZCBzcGlrZXMsIHNhd3MsIGFuZCBmYWxsaW5nIGhhemFyZHMuCkdhbWUgUnVsZXMuCi0gTW92ZSBsZWZ0L3JpZ2h0IGFuZCBqdW1wIGJldHdlZW4gcGxhdGZvcm1zLgotIFNvbWUgc2VjdGlvbnMgcmVxdWlyZSBjcm91Y2ggc2xpZGluZyBvciBkcm9wcGluZyB0aHJvdWdoIGdhcHMuCi0gRGVhdGggcmVzZXRzIHlvdSB0byBjaGVja3BvaW50cy4=)

You are playing Vex 3, a precision platformer with traps.

Game Objective.

- Reach the checkpoints and then the exit of each level.

- Avoid spikes, saws, and falling hazards.

Game Rules.

- Move left/right and jump between platforms.

- Some sections require crouch sliding or dropping through gaps.

- Death resets you to checkpoints.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIFZleCBjaGFyYWN0ZXIuIENvbnRyb2wgdGhlIHBsYXllciB0byBtb3ZlLCBqdW1wLCBhbmQgc2xpZGUuIFlvdSBhcmUgYSBwbGF0Zm9ybSBydW5uZXIuIFJlYWNoIHRoZSBleGl0IHdoaWxlIGF2b2lkaW5nIHRyYXBzLg==)

You control the Vex character. Control the player to move, jump, and slide. You are a platform runner. Reach the exit while avoiding traps.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd0xlZnQgLyBBcnJvd1JpZ2h0IG9yIEEvRDogbW92ZQotIEFycm93VXAgKyBBcnJvd0xlZnQgLyBBcnJvd1JpZ2h0OiBqdW1wIGxlZnQvcmlnaHQKLSBBcnJvd0Rvd24gKyBBcnJvd0xlZnQgLyBBcnJvd1JpZ2h0OiBjcm91Y2ggc2xpZGUgbGVmdC9yaWdodA==)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowLeft / ArrowRight or A/D: move

- ArrowUp + ArrowLeft / ArrowRight: jump left/right

- ArrowDown + ArrowLeft / ArrowRight: crouch slide left/right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkuCi0gbW92ZV9sZWZ0OiBNb3ZlIGxlZnQuCi0gbW92ZV9yaWdodDogTW92ZSByaWdodC4KLSBqdW1wOiBKdW1wLgotIGp1bXBfbGVmdDogSnVtcCBsZWZ0LgotIGp1bXBfcmlnaHQ6IEp1bXAgcmlnaHQuCi0gY3JvdWNoX3NsaWRlX2xlZnQ6IENyb3VjaCBzbGlkZSBsZWZ0LgotIGNyb3VjaF9zbGlkZV9yaWdodDogQ3JvdWNoIHNsaWRlIHJpZ2h0Lg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly.

- move\_left: Move left.

- move\_right: Move right.

- jump: Jump.

- jump\_left: Jump left.

- jump\_right: Jump right.

- crouch\_slide\_left: Crouch slide left.

- crouch\_slide\_right: Crouch slide right.

##### 31-wolf3d (Wolfenstein 3D).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFdvbGZlbnN0ZWluIDNELCBhIGZpcnN0LXBlcnNvbiBzaG9vdGVyIGdhbWUuCgpHYW1lIE9iamVjdGl2ZS4KLSBTZWFyY2ggZm9yIGFuZCBkZWZlYXQgZW5lbXkgZ3VhcmRzIGJ5IHNob290aW5nIHRoZW0uCi0gU3Vydml2ZSB3aGlsZSBtYXhpbWl6aW5nIGtpbGxzLgpHYW1lIFJ1bGVzLgotIFlvdSBjb250cm9sIGEgc29sZGllciBpbiBhIGZpcnN0LXBlcnNvbiAzRCB2aWV3LgotIEd1YXJkcyB3aWxsIHNob290IGF0IHlvdSB3aGVuIHRyaWdnZXJlZCAoc2hvdCBieSB5b3Ugb3IgeW91IGFyZSBuZWFyYnkpLCByZWR1Y2luZyB5b3VyIGhlYWx0aC4KLSBZb3Ugc3RhcnQgd2l0aCBhIHBpc3RvbCBhbmQgOCBidWxsZXRzLgotIEtpbGxlZCBndWFyZHMgbWF5IGRyb3AgYW1tbyBjbGlwcy4KLSBJZiB5b3VyIGhlYWx0aCByZWFjaGVzIDAsIHlvdSBkaWUgYW5kIHJlc3Bhd24gKGxvc2luZyBvbmUgbGlmZSkuCi0gVGhlIGdhbWUgZW5kcyB3aGVuIHlvdSBydW4gb3V0IG9mIGxpdmVzLgotIFNvbWUgZW5lbWllcyBhcmUgaW4gYW4gYWRqYWNlbnQgcm9vbSBiZWhpbmQgYSBkb29yLiBVc2UgdGhlIFNQQUNFIGtleSBuZWFyIGEgZG9vciB0byBvcGVuIGl0Lg==)

You are playing Wolfenstein 3D, a first-person shooter game.

Game Objective.

- Search for and defeat enemy guards by shooting them.

- Survive while maximizing kills.

Game Rules.

- You control a soldier in a first-person 3D view.

- Guards will shoot at you when triggered (shot by you or you are nearby), reducing your health.

- You start with a pistol and 8 bullets.

- Killed guards may drop ammo clips.

- If your health reaches 0, you die and respawn (losing one life).

- The game ends when you run out of lives.

- Some enemies are in an adjacent room behind a door. Use the SPACE key near a door to open it.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgYSBzb2xkaWVyIGluIGZpcnN0LXBlcnNvbiB2aWV3LiBTaG9vdCBndWFyZHMgdG8gZGVmZWF0IHRoZW0uIE1hbmFnZSB5b3VyIGFtbW8gYW5kIGhlYWx0aC4gVXNlIGFycm93IGtleXMgdG8gbW92ZSBhbmQgdHVybiwgWCB0byBzaG9vdCwgU1BBQ0UgdG8gb3BlbiBkb29ycy4=)

You control a soldier in first-person view. Shoot guards to defeat them. Manage your ammo and health. Use arrow keys to move and turn, X to shoot, SPACE to open doors.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VwOiBNb3ZlIGZvcndhcmQKLSBBcnJvd0Rvd246IE1vdmUgYmFja3dhcmQKLSBBcnJvd0xlZnQ6IFR1cm4gbGVmdAotIEFycm93UmlnaHQ6IFR1cm4gcmlnaHQKLSB4OiBTaG9vdCAvIEF0dGFjawotIFNwYWNlOiBVc2UgLyBPcGVuIGRvb3I=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUp: Move forward

- ArrowDown: Move backward

- ArrowLeft: Turn left

- ArrowRight: Turn right

- x: Shoot / Attack

- Space: Use / Open door

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkgdG8gb2JzZXJ2ZS4KLSBtb3ZlX2ZvcndhcmQ6IE1vdmUgZm9yd2FyZC4KLSBtb3ZlX2JhY2t3YXJkOiBNb3ZlIGJhY2t3YXJkLgotIHR1cm5fbGVmdDogVHVybiBsZWZ0LgotIHR1cm5fcmlnaHQ6IFR1cm4gcmlnaHQuCi0gc2hvb3Q6IFNob290IC8gQXR0YWNrLgotIG9wZW5fZG9vcjogVXNlIC8gT3BlbiBkb29yLg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly to observe.

- move\_forward: Move forward.

- move\_backward: Move backward.

- turn\_left: Turn left.

- turn\_right: Turn right.

- shoot: Shoot / Attack.

- open\_door: Use / Open door.

##### 32-wordle (Wordle).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFdvcmRsZSwgYSB3b3JkIGd1ZXNzaW5nIGdhbWUuCgpHYW1lIE9iamVjdGl2ZS4KLSBHdWVzcyB0aGUgaGlkZGVuIGZpdmUtbGV0dGVyIHdvcmQgaW4gc2l4IHRyaWVzLgotIFVzZSBjb2xvciBmZWVkYmFjayB0byByZWZpbmUgZ3Vlc3Nlcy4KR2FtZSBSdWxlcy4KLSBFYWNoIGd1ZXNzIG11c3QgYmUgYSB2YWxpZCBmaXZlLWxldHRlciB3b3JkLgotIEdyZWVuIG1lYW5zIGNvcnJlY3QgbGV0dGVyIGluIHRoZSBjb3JyZWN0IHBsYWNlLgotIFllbGxvdyBtZWFucyBjb3JyZWN0IGxldHRlciBpbiB0aGUgd3JvbmcgcGxhY2UuCi0gR3JheSBtZWFucyB0aGUgbGV0dGVyIGlzIG5vdCBpbiB0aGUgd29yZC4KLSBUaGUgZ3Vlc3MgaXMgYXV0by1zdWJtaXR0ZWQgd2hlbiB5b3UgdHlwZSB0aGUgNXRoIGxldHRlci4=)

You are playing Wordle, a word guessing game.

Game Objective.

- Guess the hidden five-letter word in six tries.

- Use color feedback to refine guesses.

Game Rules.

- Each guess must be a valid five-letter word.

- Green means correct letter in the correct place.

- Yellow means correct letter in the wrong place.

- Gray means the letter is not in the word.

- The guess is auto-submitted when you type the 5th letter.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIGtleWJvYXJkIGlucHV0LiBUeXBlIGEgdmFsaWQgZml2ZS1sZXR0ZXIgd29yZCB0byBtYWtlIGEgZ3Vlc3MuIFRoZSBndWVzcyBpcyBhdXRvLXN1Ym1pdHRlZCB3aGVuIDUgbGV0dGVycyBhcmUgZW50ZXJlZC4gVXNlIGNvbG9yIGZlZWRiYWNrIChncmVlbi95ZWxsb3cvZ3JheSkgdG8gbmFycm93IGRvd24gdGhlIGFuc3dlci4=)

You control the keyboard input. Type a valid five-letter word to make a guess. The guess is auto-submitted when 5 letters are entered. Use color feedback (green/yellow/gray) to narrow down the answer.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBUeXBlIGEgNS1sZXR0ZXIgd29yZCAoZS5nLiwgdHlwZSAiaGVsbG8iKS4KLSBUaGUgZ3Vlc3MgaXMgYXV0by1zdWJtaXR0ZWQgd2hlbiA1IGxldHRlcnMgYXJlIGVudGVyZWQuCi0gVXNlIEJhY2tzcGFjZSB0byBkZWxldGUgYSBsZXR0ZXI=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- Type a 5-letter word (e.g., type "hello").

- The guess is auto-submitted when 5 letters are entered.

- Use Backspace to delete a letter

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFdhaXQgYnJpZWZseS4KLSB0eXBlX3RleHQ6IFR5cGUgbGV0dGVycyBieSBzZXR0aW5nIGEgdGV4dCB2YWx1ZS4KLSBzdWJtaXRfZ3Vlc3M6IENvbmZpcm0gdGhlIGd1ZXNzIGJ5IHByZXNzaW5nIEVudGVyLg==)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Wait briefly.

- type\_text: Type letters by setting a text value.

- submit\_guess: Confirm the guess by pressing Enter.

##### 33-worlds-hardest-game (World’s Hardest Game).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFdvcmxkJ3MgSGFyZGVzdCBHYW1lLCBhIHByZWNpc2lvbiBtYXplIGRvZGdlIGdhbWUuCgpHYW1lIE9iamVjdGl2ZS4KLSBDb2xsZWN0IGFsbCBjb2lucyBpbiB0aGUgbGV2ZWwuCi0gUmVhY2ggdGhlIGdyZWVuIGV4aXQgem9uZSB0byBjb21wbGV0ZSB0aGUgbGV2ZWwuCkdhbWUgUnVsZXMuCi0gWW91IGNvbnRyb2wgYSByZWQgc3F1YXJlIGluIGEgbWF6ZS4KLSBCbHVlIGVuZW1pZXMgbW92ZSBvbiBmaXhlZCBwYXRocyBhbmQga2lsbCB5b3Ugb24gY29udGFjdC4KLSBDaGVja3BvaW50cyBzYXZlIHByb2dyZXNzIGFmdGVyIGNvbGxlY3RpbmcgaXRlbXMuIFVzZSBjaGVja3BvaW50cyB0byBzcGxpdCB0aGUgbGV2ZWwgaW50byBzYWZlIHNlZ21lbnRzLgotIE9ic2VydmUgZW5lbXkgY3ljbGVzIGNhcmVmdWxseSB0byBhdm9pZCB0aGVtLg==)

You are playing World’s Hardest Game, a precision maze dodge game.

Game Objective.

- Collect all coins in the level.

- Reach the green exit zone to complete the level.

Game Rules.

- You control a red square in a maze.

- Blue enemies move on fixed paths and kill you on contact.

- Checkpoints save progress after collecting items. Use checkpoints to split the level into safe segments.

- Observe enemy cycles carefully to avoid them.

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHJlZCBzcXVhcmUuIE1vdmUgdG8gY29sbGVjdCBjb2lucyBhbmQgcmVhY2ggdGhlIGV4aXQgd2hpbGUgYXZvaWRpbmcgZW5lbWllcy4gQXZvaWQgYmx1ZSBlbmVtaWVzLCBjb2xsZWN0IGFsbCBjb2lucywgYW5kIHJlYWNoIHRoZSBncmVlbiBleGl0Lg==)

You control the red square. Move to collect coins and reach the exit while avoiding enemies. Avoid blue enemies, collect all coins, and reach the green exit.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VwOiBNb3ZlIHVwCi0gQXJyb3dEb3duOiBNb3ZlIGRvd24KLSBBcnJvd0xlZnQ6IE1vdmUgbGVmdAotIEFycm93UmlnaHQ6IE1vdmUgcmlnaHQ=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUp: Move up

- ArrowDown: Move down

- ArrowLeft: Move left

- ArrowRight: Move right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkgdG8gb2JzZXJ2ZS4KLSBtb3ZlX3VwOiBNb3ZlIHVwLgotIG1vdmVfZG93bjogTW92ZSBkb3duLgotIG1vdmVfbGVmdDogTW92ZSBsZWZ0LgotIG1vdmVfcmlnaHQ6IE1vdmUgcmlnaHQu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly to observe.

- move\_up: Move up.

- move\_down: Move down.

- move\_left: Move left.

- move\_right: Move right.

##### 34-worlds-hardest-game-2 (World’s Hardest Game 2).

Game Rules Prompt.

[⬇](data:text/plain;base64,WW91IGFyZSBwbGF5aW5nIFdvcmxkJ3MgSGFyZGVzdCBHYW1lLCBhIHByZWNpc2lvbiBtYXplIGRvZGdlIGdhbWUuCgpHYW1lIE9iamVjdGl2ZS4KLSBDb2xsZWN0IGFsbCBjb2lucyBpbiB0aGUgbGV2ZWwuCi0gUmVhY2ggdGhlIGdyZWVuIGV4aXQgem9uZSB0byBjb21wbGV0ZSB0aGUgbGV2ZWwuCkdhbWUgUnVsZXMuCi0gWW91IGNvbnRyb2wgYSByZWQgc3F1YXJlIGluIGEgbWF6ZS4KLSBCbHVlIGVuZW1pZXMgbW92ZSBvbiBmaXhlZCBwYXRocyBhbmQga2lsbCB5b3Ugb24gY29udGFjdC4KLSBPYnNlcnZlIGVuZW15IGN5Y2xlcyBjYXJlZnVsbHkgdG8gYXZvaWQgdGhlbQ==)

You are playing World’s Hardest Game, a precision maze dodge game.

Game Objective.

- Collect all coins in the level.

- Reach the green exit zone to complete the level.

Game Rules.

- You control a red square in a maze.

- Blue enemies move on fixed paths and kill you on contact.

- Observe enemy cycles carefully to avoid them

Role 0 (player) Game Agent Role Prompt.

[⬇](data:text/plain;base64,WW91IGNvbnRyb2wgdGhlIHJlZCBzcXVhcmUuIE1vdmUgdG8gY29sbGVjdCBpdGVtcyBhbmQgcmVhY2ggdGhlIGV4aXQgd2hpbGUgYXZvaWRpbmcgZW5lbWllcy4gQXZvaWQgYmx1ZSBlbmVtaWVzLCBjb2xsZWN0IGFsbCBpdGVtcywgYW5kIHJlYWNoIHRoZSBncmVlbiBleGl0Lg==)

You control the red square. Move to collect items and reach the exit while avoiding enemies. Avoid blue enemies, collect all items, and reach the green exit.

Role 0 (player) Computer-Use Controls Prompt.

[⬇](data:text/plain;base64,QUNUSU9OIFNQQUNFIChPTkxZIExFR0FMIEFDVElPTlMpOgoKLSBBcnJvd1VwOiBNb3ZlIHVwCi0gQXJyb3dEb3duOiBNb3ZlIGRvd24KLSBBcnJvd0xlZnQ6IE1vdmUgbGVmdAotIEFycm93UmlnaHQ6IE1vdmUgcmlnaHQ=)

ACTION SPACE (ONLY LEGAL ACTIONS):

- ArrowUp: Move up

- ArrowDown: Move down

- ArrowLeft: Move left

- ArrowRight: Move right

Role 0 (player) Generalist Semantic Action List.

[⬇](data:text/plain;base64,UkVHSVNURVJFRCBBQ1RJT05TIChTZW1hbnRpYyBDb250cm9scykuCkNob29zZSBleGFjdGx5IG9uZSBhY3Rpb24gcGVyIHN0ZXA6CgotIHdhaXQ6IFBhdXNlIGJyaWVmbHkgdG8gb2JzZXJ2ZS4KLSBtb3ZlX3VwOiBNb3ZlIHVwLgotIG1vdmVfZG93bjogTW92ZSBkb3duLgotIG1vdmVfbGVmdDogTW92ZSBsZWZ0LgotIG1vdmVfcmlnaHQ6IE1vdmUgcmlnaHQu)

REGISTERED ACTIONS (Semantic Controls).

Choose exactly one action per step:

- wait: Pause briefly to observe.

- move\_up: Move up.

- move\_down: Move down.

- move\_left: Move left.

- move\_right: Move right.

### 12.3 Model Output-Format Blocks

Below we list the exact output\_format block from each registered model specification.

##### Claude-Sonnet-4.6 (Computer-Use).

[⬇](data:text/plain;base64,LSBVc2UgdGhlIENsYXVkZSBjb21wdXRlci11c2UgdG9vbCB0byByZXR1cm4gZXhhY3RseSBvbmUgYWN0aW9uIG9yIGtleSBjb21iaW5hdGlvbiBwZXIgc3RlcC4KLSBZb3UgYXJlIG5vdCBhbGxvd2VkIHRvIHRha2Ugc2NyZWVuc2hvdHMgb24geW91ciBvd24uCi0gRG8gbm90IG91dHB1dCBmcmVlLWZvcm0gdGV4dCBvdXRzaWRlIHRvb2wgY2FsbHMu)

- Use the Claude computer-use tool to return exactly one action or key combination per step.

- You are not allowed to take screenshots on your own.

- Do not output free-form text outside tool calls.

##### Claude-Sonnet-4.6 (Generalist).

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAuCi0gVGhlIHRvb2wgbmFtZSBtdXN0IGJlIGEgcmVnaXN0ZXJlZCBhY3Rpb24gaWQuCi0gSW5jbHVkZSBgcmVhc29uaW5nYCBhcyBhIHNob3J0IHJhdGlvbmFsZS4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0Lg==)

- You must call exactly ONE tool per step.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### Gemini-2.5-Computer-Use.

[⬇](data:text/plain;base64,LSBVc2UgdGhlIGJ1aWx0LWluIGNvbXB1dGVyLXVzZSB0b29sIHRvIHJldHVybiBvbmUgYWN0aW9uIG9yIGtleSBjb21iaW5hdGlvbiBwZXIgc3RlcC4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0IG91dHNpZGUgdG9vbCBjYWxscy4=)

- Use the built-in computer-use tool to return one action or key combination per step.

- Do not output free-form text outside tool calls.

##### Gemini-3-Flash-Preview.

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAuCi0gVGhlIHRvb2wgbmFtZSBtdXN0IGJlIGEgcmVnaXN0ZXJlZCBhY3Rpb24gaWQuCi0gSW5jbHVkZSBgcmVhc29uaW5nYCBhcyBhIHNob3J0IHJhdGlvbmFsZS4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0Lg==)

- You must call exactly ONE tool per step.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### GLM-4.6V.

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAgd2l0aCB0b29sX2NhbGxzLgotIFRoZSB0b29sIG5hbWUgbXVzdCBiZSBhIHJlZ2lzdGVyZWQgYWN0aW9uIGlkLgotIEluY2x1ZGUgYHJlYXNvbmluZ2AgYXMgYSBzaG9ydCByYXRpb25hbGUuCi0gRG8gbm90IG91dHB1dCBmcmVlLWZvcm0gdGV4dC4=)

- You must call exactly ONE tool per step with tool\_calls.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### Grok-4.1-Fast-Reasoning.

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAuCi0gVGhlIHRvb2wgbmFtZSBtdXN0IGJlIGEgcmVnaXN0ZXJlZCBhY3Rpb24gaWQuCi0gSW5jbHVkZSBgcmVhc29uaW5nYCBhcyBhIHNob3J0IHJhdGlvbmFsZS4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0Lg==)

- You must call exactly ONE tool per step.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### Kimi-K2.5.

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAuCi0gVGhlIHRvb2wgbmFtZSBtdXN0IGJlIGEgcmVnaXN0ZXJlZCBhY3Rpb24gaWQuCi0gSW5jbHVkZSBgcmVhc29uaW5nYCBhcyBhIHNob3J0IHJhdGlvbmFsZS4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0Lg==)

- You must call exactly ONE tool per step.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### Qwen3-VL-235B-A22B (Computer-Use).

[⬇](data:text/plain;base64,UmVzcG9uc2UgZm9ybWF0IGZvciBldmVyeSBzdGVwOgpBIDx0aGluaz4gLi4uIDwvdGhpbms+IGJsb2NrIG9mIGEgdmVyeSBzaG9ydCBzZW50ZW5jZSBkZXNjcmliaW5nIHdoYXQgdG8gZG8uCkEgc2luZ2xlIDx0b29sX2NhbGw+Li4uPC90b29sX2NhbGw+IGJsb2NrIGNvbnRhaW5pbmcgb25seSB0aGUgSlNPTjogeyJuYW1lIjogIjxmdW5jdGlvbi1uYW1lPiIsICJhcmd1bWVudHMiOiA8YXJncy1qc29uLW9iamVjdD59CgpVc2UgdGhlIGBjb21wdXRlcl91c2VgIHRvb2wgY2FsbCBhbmQgcmV0dXJuIGV4YWN0bHkgb25lIGFjdGlvbiBwZXIgc3RlcC4KVXNlIG9ubHkgdGhlIDx0aGluaz4gYW5kIHRoZSA8dG9vbF9jYWxsPiBibG9jazsgZG8gbm90IGFkZCBhbnkgb3RoZXIgdGV4dC4=)

Response format for every step:

A <think> ... </think> block of a very short sentence describing what to do.

A single <tool\_call>...</tool\_call> block containing only the JSON: {"name": "<function-name>", "arguments": <args-json-object>}

Use the ‘computer\_use‘ tool call and return exactly one action per step.

Use only the <think> and the <tool\_call> block; do not add any other text.

##### Qwen3-VL-235B-A22B (Generalist).

[⬇](data:text/plain;base64,UmVzcG9uc2UgZm9ybWF0IGZvciBldmVyeSBzdGVwOgpBIDx0aGluaz4gLi4uIDwvdGhpbms+IGJsb2NrIG9mIGEgdmVyeSBzaG9ydCBzZW50ZW5jZSBkZXNjcmliaW5nIHdoYXQgdG8gZG8uCkEgc2luZ2xlIDx0b29sX2NhbGw+Li4uPC90b29sX2NhbGw+IGJsb2NrIGNvbnRhaW5pbmcgb25seSB0aGUgSlNPTjogeyJuYW1lIjogIjxmdW5jdGlvbi1uYW1lPiIsICJhcmd1bWVudHMiOiA8YXJncy1qc29uLW9iamVjdD59CgpVc2Ugb25seSB0aGUgPHRoaW5rPiBhbmQgdGhlIDx0b29sX2NhbGw+IGJsb2NrOyBkbyBub3QgYWRkIGFueSBvdGhlciB0ZXh0Lg==)

Response format for every step:

A <think> ... </think> block of a very short sentence describing what to do.

A single <tool\_call>...</tool\_call> block containing only the JSON: {"name": "<function-name>", "arguments": <args-json-object>}

Use only the <think> and the <tool\_call> block; do not add any other text.

##### Qwen3-VL-30B-A3B (Computer-Use).

[⬇](data:text/plain;base64,UmVzcG9uc2UgZm9ybWF0IGZvciBldmVyeSBzdGVwOgpBIDx0aGluaz4gLi4uIDwvdGhpbms+IGJsb2NrIG9mIGEgdmVyeSBzaG9ydCBzZW50ZW5jZSBkZXNjcmliaW5nIHdoYXQgdG8gZG8uCkEgc2luZ2xlIDx0b29sX2NhbGw+Li4uPC90b29sX2NhbGw+IGJsb2NrIGNvbnRhaW5pbmcgb25seSB0aGUgSlNPTjogeyJuYW1lIjogIjxmdW5jdGlvbi1uYW1lPiIsICJhcmd1bWVudHMiOiA8YXJncy1qc29uLW9iamVjdD59CgpVc2UgdGhlIGBjb21wdXRlcl91c2VgIHRvb2wgY2FsbCBhbmQgcmV0dXJuIGV4YWN0bHkgb25lIGFjdGlvbiBwZXIgc3RlcC4KVXNlIG9ubHkgdGhlIDx0aGluaz4gYW5kIHRoZSA8dG9vbF9jYWxsPiBibG9jazsgZG8gbm90IGFkZCBhbnkgb3RoZXIgdGV4dC4=)

Response format for every step:

A <think> ... </think> block of a very short sentence describing what to do.

A single <tool\_call>...</tool\_call> block containing only the JSON: {"name": "<function-name>", "arguments": <args-json-object>}

Use the ‘computer\_use‘ tool call and return exactly one action per step.

Use only the <think> and the <tool\_call> block; do not add any other text.

##### Qwen3-VL-30B-A3B (Generalist).

[⬇](data:text/plain;base64,UmVzcG9uc2UgZm9ybWF0IGZvciBldmVyeSBzdGVwOgpBIDx0aGluaz4gLi4uIDwvdGhpbms+IGJsb2NrIG9mIGEgdmVyeSBzaG9ydCBzZW50ZW5jZSBkZXNjcmliaW5nIHdoYXQgdG8gZG8uCkEgc2luZ2xlIDx0b29sX2NhbGw+Li4uPC90b29sX2NhbGw+IGJsb2NrIGNvbnRhaW5pbmcgb25seSB0aGUgSlNPTjogeyJuYW1lIjogIjxmdW5jdGlvbi1uYW1lPiIsICJhcmd1bWVudHMiOiA8YXJncy1qc29uLW9iamVjdD59CgpVc2Ugb25seSB0aGUgPHRoaW5rPiBhbmQgdGhlIDx0b29sX2NhbGw+IGJsb2NrOyBkbyBub3QgYWRkIGFueSBvdGhlciB0ZXh0Lg==)

Response format for every step:

A <think> ... </think> block of a very short sentence describing what to do.

A single <tool\_call>...</tool\_call> block containing only the JSON: {"name": "<function-name>", "arguments": <args-json-object>}

Use only the <think> and the <tool\_call> block; do not add any other text.

##### OpenAI-Computer-Use.

[⬇](data:text/plain;base64,LSBVc2UgdGhlIGNvbXB1dGVyLXVzZSB0b29sIHRvIHJldHVybiBleGFjdGx5IG9uZSBhY3Rpb24gb3Iga2V5IGNvbWJpbmF0aW9uIHBlciBzdGVwLgotIERvIG5vdCBvdXRwdXQgZnJlZS1mb3JtIHRleHQgb3V0c2lkZSB0b29sIGNhbGxzLgotIERvIG5vdCB0YWtlIHNjcmVlbnNob3RzIG9uIHlvdXIgb3duLg==)

- Use the computer-use tool to return exactly one action or key combination per step.

- Do not output free-form text outside tool calls.

- Do not take screenshots on your own.

##### GPT-5.2.

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAuCi0gVGhlIHRvb2wgbmFtZSBtdXN0IGJlIGEgcmVnaXN0ZXJlZCBhY3Rpb24gaWQuCi0gSW5jbHVkZSBgcmVhc29uaW5nYCBhcyBhIHNob3J0IHJhdGlvbmFsZS4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0Lg==)

- You must call exactly ONE tool per step.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### Qwen3-VL-Plus (Computer-Use).

[⬇](data:text/plain;base64,LSBVc2UgdGhlIGBjb21wdXRlcl91c2VgIHRvb2wgY2FsbCBhbmQgcmV0dXJuIGV4YWN0bHkgb25lIGFjdGlvbiBvciBrZXkgY29tYmluYXRpb24gcGVyIHN0ZXAuCi0gRG8gbm90IG91dHB1dCBmcmVlLWZvcm0gdGV4dCBvdXRzaWRlIDx0b29sX2NhbGw+IGJsb2Nrcy4=)

- Use the ‘computer\_use‘ tool call and return exactly one action or key combination per step.

- Do not output free-form text outside <tool\_call> blocks.

##### Qwen3-VL-Plus (Generalist).

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAuCi0gVGhlIHRvb2wgbmFtZSBtdXN0IGJlIGEgcmVnaXN0ZXJlZCBhY3Rpb24gaWQuCi0gSW5jbHVkZSBgcmVhc29uaW5nYCBhcyBhIHNob3J0IHJhdGlvbmFsZS4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0Lg==)

- You must call exactly ONE tool per step.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### Seed-1.8 (Computer-Use).

[⬇](data:text/plain;base64,QUNUSU9OIEZPUk1BVCAodXNlIGV4YWN0bHkgdGhpcyBzeW50YXgpOgotIFByZXNzIHNpbmdsZSBrZXk6IGhvdGtleShrZXk9JzxrZXk+JykKLSBQcmVzcyBtdWx0aXBsZSBrZXlzOiBob3RrZXkoa2V5PSc8a2V5MT4gPGtleTI+JykKLSBDbGljayBhdCBwb3NpdGlvbjogY2xpY2socG9pbnQ9Jzxwb2ludD54IHk8L3BvaW50PicpCi0gUmlnaHQgY2xpY2sgYXQgcG9zaXRpb246IHJpZ2h0X3NpbmdsZShwb2ludD0nPHBvaW50PnggeTwvcG9pbnQ+JykKLSBXYWl0L29ic2VydmU6IHdhaXQoKQoKRXhhbXBsZXM6Ci0gaG90a2V5KGtleT0ndycpICAgICAgICAgICAjIFByZXNzIFcKLSBob3RrZXkoa2V5PSd3IGQnKSAgICAgICAgICMgUHJlc3MgVyBhbmQgRCB0b2dldGhlciAoanVtcCByaWdodCkKLSBob3RrZXkoa2V5PSdhcnJvd3VwJykgICAgICMgUHJlc3MgVXAgYXJyb3cKLSBjbGljayhwb2ludD0nPHBvaW50PjY0MCAzNjA8L3BvaW50PicpICAjIENsaWNrIGF0IGNlbnRlcgotIHJpZ2h0X3NpbmdsZShwb2ludD0nPHBvaW50PjY0MCAzNjA8L3BvaW50PicpICAjIFJpZ2h0IGNsaWNrIGF0IGNlbnRlcg==)

ACTION FORMAT (use exactly this syntax):

- Press single key: hotkey(key=’<key>’)

- Press multiple keys: hotkey(key=’<key1> <key2>’)

- Click at position: click(point=’<point>x y</point>’)

- Right click at position: right\_single(point=’<point>x y</point>’)

- Wait/observe: wait()

Examples:

- hotkey(key=’w’) # Press W

- hotkey(key=’w d’) # Press W and D together (jump right)

- hotkey(key=’arrowup’) # Press Up arrow

- click(point=’<point>640 360</point>’) # Click at center

- right\_single(point=’<point>640 360</point>’) # Right click at center

##### Seed-1.8 (Generalist).

[⬇](data:text/plain;base64,LSBZb3UgbXVzdCBjYWxsIGV4YWN0bHkgT05FIHRvb2wgcGVyIHN0ZXAuCi0gVGhlIHRvb2wgbmFtZSBtdXN0IGJlIGEgcmVnaXN0ZXJlZCBhY3Rpb24gaWQuCi0gSW5jbHVkZSBgcmVhc29uaW5nYCBhcyBhIHNob3J0IHJhdGlvbmFsZS4KLSBEbyBub3Qgb3V0cHV0IGZyZWUtZm9ybSB0ZXh0Lg==)

- You must call exactly ONE tool per step.

- The tool name must be a registered action id.

- Include ‘reasoning‘ as a short rationale.

- Do not output free-form text.

##### UI-TARS-1.5-7B.

[⬇](data:text/plain;base64,QUNUSU9OIEZPUk1BVCAodXNlIGV4YWN0bHkgdGhpcyBzeW50YXgpOgotIFByZXNzIHNpbmdsZSBrZXk6IGhvdGtleShrZXk9JzxrZXk+JykKLSBQcmVzcyBtdWx0aXBsZSBrZXlzOiBob3RrZXkoa2V5PSc8a2V5MT4gPGtleTI+JykKLSBDbGljayBhdCBwb3NpdGlvbjogY2xpY2socG9pbnQ9Jzxwb2ludD54IHk8L3BvaW50PicpCi0gUmlnaHQgY2xpY2sgYXQgcG9zaXRpb246IHJpZ2h0X3NpbmdsZShwb2ludD0nPHBvaW50PnggeTwvcG9pbnQ+JykKLSBXYWl0L29ic2VydmU6IHdhaXQoKQoKRXhhbXBsZXM6Ci0gaG90a2V5KGtleT0ndycpICAgICAgICAgICAjIFByZXNzIFcKLSBob3RrZXkoa2V5PSd3IGQnKSAgICAgICAgICMgUHJlc3MgVyBhbmQgRCB0b2dldGhlciAoanVtcCByaWdodCkKLSBob3RrZXkoa2V5PSdhcnJvd3VwJykgICAgICMgUHJlc3MgVXAgYXJyb3cKLSBjbGljayhwb2ludD0nPHBvaW50PjY0MCAzNjA8L3BvaW50PicpICAjIENsaWNrIGF0IGNlbnRlcgotIHJpZ2h0X3NpbmdsZShwb2ludD0nPHBvaW50PjY0MCAzNjA8L3BvaW50PicpICAjIFJpZ2h0IGNsaWNrIGF0IGNlbnRlcg==)

ACTION FORMAT (use exactly this syntax):

- Press single key: hotkey(key=’<key>’)

- Press multiple keys: hotkey(key=’<key1> <key2>’)

- Click at position: click(point=’<point>x y</point>’)

- Right click at position: right\_single(point=’<point>x y</point>’)

- Wait/observe: wait()

Examples:

- hotkey(key=’w’) # Press W

- hotkey(key=’w d’) # Press W and D together (jump right)

- hotkey(key=’arrowup’) # Press Up arrow

- click(point=’<point>640 360</point>’) # Click at center

- right\_single(point=’<point>640 360</point>’) # Right click at center

## 13 Costs and Licensing Considerations

##### Licensing Considerations.

GameWorld spans both proprietary and open-source browser games. We are sincerely grateful to the original game creators and rights holders whose work makes this benchmark possible. Our release policy is designed to respect upstream authorship, licensing terms, and distribution requirements. In particular, users are responsible for purchasing or obtaining lawful access to any benchmarked game. Any game access or distribution must comply with the applicable licenses and permissions.

Here we explicitly state the following licensing and compliance guidelines: "*This project is intended strictly for research and benchmarking purposes. It does not grant any rights to access, reproduce, distribute, modify, or commercially use third-party games or related assets beyond those permitted by applicable licenses, terms of service, and law. Users are solely responsible for purchasing or obtaining lawful access and any necessary permissions for evaluation, dataset creation, model development, or downstream use.*"

##### Cost Summary.

Table 13: Estimated benchmark cost of evaluating all 170 tasks for each model. Input / output token counts are averaged per step.

|  |  |  |  |
| --- | --- | --- | --- |
| Model | Input Tokens / Step | Output Tokens / Step | Total Cost (USD) |
| Claude-Sonnet-4.6 (Computer-Use) | 3344.9 | 131.7 | 172.46 |
| Claude-Sonnet-4.6 (Generalist) | 4865.8 | 86.3 | 244.03 |
| Gemini-2.5-Computer-Use | 2086.6 | 15.4 | 41.06 |
| Gemini-3-Flash-Preview | 4005.6 | 40.5 | 29.13 |
| GLM-4.6V | 4820.2 | 253.2 | 24.79 |
| GPT-5.2 | 3924.6 | 38.9 | 110.68 |
| Grok-4.1-Fast-Reasoning | 2551.1 | 907.7 | 9.86 |
| Kimi-K2.5 | 5030.9 | 250.0 | 45.77 |
| OpenAI-Computer-Use | 1684.4 | 87.2 | 94.65 |
| Qwen3-VL-Plus (Computer-Use) | 2112.3 | 27.7 | 4.99 |
| Qwen3-VL-Plus (Generalist) | 3675.1 | 61.3 | 9.01 |
| Seed-1.8 (Computer-Use) | 2184.0 | 210.6 | 13.91 |
| Seed-1.8 (Generalist) | 2642.6 | 179.9 | 14.85 |
| Total Cost (all listed models) | | | 815.19 |

Table [13](https://arxiv.org/html/2604.07429v1#S13.T13 "Table 13 ‣ Cost Summary. ‣ 13 Costs and Licensing Considerations ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents") reports average input and output tokens *per step*, together with the estimated total dollar cost for evaluating all 170 benchmark tasks.
For the input-token column, we include cached input tokens when present, i.e., per\_step\_input + per\_step\_cache if the model API supports caching.
The total cost column is the measured average cost per task from all the trace logs.
The underlying model pricing estimates are taken from the pricing snapshot recorded on March 7, 2026.
The cost for open-weight models, including Qwen3-VL-235B-A22B, Qwen3-VL-30B-A3B, and UI-TARS-1.5-7B, is not included in the calculation.
The final total cost for evaluating all 170 tasks across all listed models is 815.19 USD.

## References

* [1]
  M. Abernethy (2006)
  Cubefield.
   Max Abernethy.
  Note: Flash game (preserved on Internet Archive)
  External Links: [Link](https://archive.org/details/cubefield_flash)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.10.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [2]
  A. Adam (2014)
  Vex 3.
   Amazing Adam.
  Note: Browser platform game
  External Links: [Link](https://apps.microsoft.com/detail/9ntlfr2tdg7z)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.7.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [3]
  J. Ahn, J. Kim, H. Yun, J. Son, D. Park, J. Cho, and G. Kim (2025)
  FlashAdventure: a benchmark for gui agents solving full story arcs in diverse adventure games.
  In EMNLP,
  Cited by: [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.9.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [4]
  O. Albet (2009)
  Fireboy and watergirl.
   Oslo Albet.
  Note: Flash puzzle-platform game
  External Links: [Link](https://en.wikipedia.org/wiki/Fireboy_and_Watergirl)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.13.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [5]
  Anthropic (2024)
  Claude: constitutional ai models from anthropic.
  Note: <https://www.anthropic.com/claude>Official description of the Claude model family
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.3.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [6]
  Atari, Inc. (1976)
  Breakout.
   Atari, Inc..
  Note: Arcade game manual (preserved digital artifact)
  External Links: [Link](https://archive.org/details/ArcadeGameManualBreakout)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.6.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [7]
  H. Bai, A. Taymanov, T. Zhang, A. Kumar, and S. Whitehead (2026)
  WebGym: scaling training environments for visual web agents with realistic tasks.
  External Links: 2601.02439
  Cited by: [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
<a id="bib.bib21"></a>* [8]
  S. Bai, Y. Cai, R. Chen, K. Chen, X. Chen, Z. Cheng, L. Deng, W. Ding, C. Gao, C. Ge, W. Ge, Z. Guo, Q. Huang, J. Huang, F. Huang, B. Hui, S. Jiang, Z. Li, M. Li, M. Li, K. Li, Z. Lin, J. Lin, X. Liu, J. Liu, C. Liu, Y. Liu, D. Liu, S. Liu, D. Lu, R. Luo, C. Lv, R. Men, L. Meng, X. Ren, X. Ren, S. Song, Y. Sun, J. Tang, J. Tu, J. Wan, P. Wang, P. Wang, Q. Wang, Y. Wang, T. Xie, Y. Xu, H. Xu, J. Xu, Z. Yang, M. Yang, J. Yang, A. Yang, B. Yu, F. Zhang, H. Zhang, X. Zhang, B. Zheng, H. Zhong, J. Zhou, F. Zhou, J. Zhou, Y. Zhu, and K. Zhu (2025)
  Qwen3-vl technical report.
  arXiv preprint arXiv:2511.21631.
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.11.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.14.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.15.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [2nd item](https://arxiv.org/html/2604.07429v1#S4.I1.i2.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [9]
  B. Baker, I. Akkaya, P. Zhokov, J. Huizinga, J. Tang, A. Ecoffet, B. Houghton, R. Sampedro, and J. Clune (2022)
  Video pretraining (vpt): learning to act by watching unlabeled online videos.
  Advances in Neural Information Processing Systems 35, pp. 24639–24654.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [10]
  A. Bakhtin, N. Brown, E. Dinan, G. Farina, C. Flaherty, D. Fried, A. Goff, J. Gray, H. Hu, et al. (2022)
  Human-level play in the game of diplomacy by combining language models with strategic reasoning.
  Science 378 (6624), pp. 1067–1074.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [11]
  C. Beattie, J. Z. Leibo, D. Teplyashin, T. Ward, M. Wainwright, H. Küttler, A. Lefrancq, S. Green, V. Valdés, A. Sadik, et al. (2016)
  Deepmind lab.
  arXiv preprint arXiv:1612.03801.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [12]
  G. Brockman, V. Cheung, L. Pettersson, J. Schneider, J. Schulman, J. Tang, and W. Zaremba (2016)
  OpenAI gym.
  External Links: arXiv:1606.01540
  Cited by: [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [13]
  G. Cirulli (2014)
  2048.
   Gabriele Cirulli.
  Note: GitHub repository (browser game)
  External Links: [Link](https://github.com/gabrielecirulli/2048)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.2.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [14]
  J. Cloutier (2014)
  Run 3.
   Player\_03.
  Note: Browser game
  External Links: [Link](https://player03.com/run/3/beta/)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.3.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [15]
  Coolmath Games (2018)
  Another gentleman’s adventure.
   Coolmath Games.
  Note: Browser game page (Coolmath Games)
  External Links: [Link](https://www.coolmathgames.com/0-another-gentlemans-adventure)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.3.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [16]
  M. Côté, A. Kádár, X. Yuan, B. Kybartas, T. Barnes, E. Fine, J. Moore, M. Hausknecht, L. El Asri, M. Adada, et al. (2019)
  Textworld: a learning environment for text-based games.
  In Computer Games: 7th Workshop, CGW 2018, Held in Conjunction with the 27th International Conference on Artificial Intelligence, IJCAI 2018, Stockholm, Sweden, July 13, 2018, Revised Selected Papers 7,
  pp. 41–75.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [17]
  S. Critoph (2007)
  The world’s hardest game.
   Armor Games.
  Note: Flash game
  External Links: [Link](https://en.wikipedia.org/wiki/The_World%27s_Hardest_Game)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.10.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [18]
  S. Critoph (2008)
  The world’s hardest game 2.
   Snubby Land.
  Note: Flash game
  External Links: [Link](https://archive.org/details/worldshardestgame2_202310)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.11.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [19]
  J. DeBenedetto (2017)
  Boxel rebound.
   Doppler Creative.
  Note: Browser game / extension distribution (official developer site)
  External Links: [Link](https://www.dopplercreative.com/boxel-rebound/privacy-policy)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.5.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [20]
  Dedra Games (2018)
  OvO.
   Dedra Games.
  Note: Google Play app listing
  External Links: [Link](https://play.google.com/store/apps/details?id=com.dedra.ovo)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.11.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [21]
  X. Deng, Y. Gu, B. Zheng, S. Chen, S. Stevens, B. Wang, H. Sun, and Y. Su (2023)
  Mind2Web: towards a generalist agent for the web.
  In Thirty-seventh Conference on Neural Information Processing Systems,
  External Links: [Link](https://openreview.net/forum?id=kiYqbO3wqw)
  Cited by: [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [22]
  C. Ebberson (2021)
  The adventures of captain callisto.
   JS13K Games.
  Note: JS13K Games entry (browser game)
  External Links: [Link](https://js13kgames.com/entries/the-adventures-of-captain-callisto)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.7.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [23]
  L. Fan, G. Wang, Y. Jiang, A. Mandlekar, Y. Yang, H. Zhu, A. Tang, D. Huang, Y. Zhu, and A. Anandkumar (2022)
  Minedojo: building open-ended embodied agents with internet-scale knowledge.
  Advances in Neural Information Processing Systems 35, pp. 18343–18362.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [24]
  K. Franz (2013)
  FullScreenMario.
   karol-f.
  Note: GitHub repository (browser game engine/implementation)
  External Links: [Link](https://github.com/karol-f/FullScreenMario)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.6.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [25]
  D. Gao, L. Ji, Z. Bai, M. Ouyang, P. Li, D. Mao, Q. Wu, W. Zhang, P. Wang, X. Guo, et al. (2023)
  Assistgui: task-oriented desktop graphical user interface automation.
  arXiv preprint arXiv:2312.13108.
  Cited by: [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [26]
  Gemini Team (2025)
  Gemini: a family of highly capable multimodal models.
  External Links: 2312.11805,
  [Link](https://arxiv.org/abs/2312.11805)
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.5.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [27]
  Google Chrome team (2014)
  Chrome dino (offline dinosaur game).
   Google.
  Note: Built-in browser game in Google Chrome
  External Links: [Link](https://blog.google/products-and-platforms/products/chrome/chrome-dino/)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.8.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [28]
  Google LLC (2013)
  Google snake.
   Google LLC.
  Note: Google Doodle browser game
  External Links: [Link](https://www.google.com/fbx?fbx=snake_arcade)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.4.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [29]
  Google (2025)
  Gemini 2.5 computer use model card.
  Note: <https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-2-5-Computer-Use-Model-Card.pdf>System card describing the Gemini 2.5 Computer Use model
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.4.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [30]
  D. Guo, F. Wu, F. Zhu, F. Leng, G. Shi, H. Chen, H. Fan, J. Wang, J. Jiang, J. Wang, et al. (2025)
  Seed1. 5-vl technical report.
  arXiv preprint arXiv:2505.07062.
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.12.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [31]
  Hextris contributors (2014)
  Hextris.
   Hextris project.
  Note: GitHub repository (browser game)
  External Links: [Link](https://github.com/Hextris/hextris)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.5.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [32]
  W. Hong, W. Yu, X. Gu, G. Wang, G. Gan, H. Tang, J. Cheng, J. Qi, J. Ji, L. Pan, et al. (2025)
  Glm-4.5 v and glm-4.1 v-thinking: towards versatile multimodal reasoning with scalable reinforcement learning.
  arXiv preprint arXiv:2507.01006.
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.6.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [33]
  L. Hu, M. Huo, Y. Zhang, H. Yu, E. P. Xing, I. Stoica, T. Rosing, H. Jin, and H. Zhang (2025)
  Lmgame-bench: how good are llms at playing games?.
  External Links: 2505.15146
  Cited by: [§1](https://arxiv.org/html/2604.07429v1#S1.p2.1 "1 Introduction ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§2.4](https://arxiv.org/html/2604.07429v1#S2.SS4.p1.1 "2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.7.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [34]
  S. Hu, M. Ouyang, D. Gao, and M. Z. Shou (2024)
  The dawn of gui agent: a preliminary case study with claude 3.5 computer use.
  arXiv preprint arXiv:2411.10323.
  Cited by: [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [35]
  IdeiGeniale (2025)
  GeoDash 2.2.
   IdeiGeniale.
  Note: GitHub repository (browser game)
  External Links: [Link](https://github.com/IdeiGeniale/GeoDash2.2)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.3.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [36]
  Imangi Studios (2013)
  Temple run 2.
   Imangi Studios.
  Note: Google Play listing
  External Links: [Link](https://play.google.com/store/apps/details?id=com.imangi.templerun2)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.5.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [37]
  T. Iwatani (1980)
  PAC-man.
   Bandai Namco.
  Note: Official franchise history page
  External Links: [Link](https://pacman.com/en/history/)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.12.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [38]
  H. Jia, J. Liao, X. Zhang, H. Xu, T. Xie, C. Jiang, M. Yan, S. Liu, W. Ye, and F. Huang (2025)
  OSWorld-mcp: benchmarking mcp tool invocation in computer-use agents.
  External Links: 2510.24563
  Cited by: [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [39]
  Ketchapp (2016)
  Stack.
   Ketchapp.
  Note: App Store listing
  External Links: [Link](https://apps.apple.com/us/app/stack/id1080487957)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.4.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [40]
  Leko (2020)
  Restless wing syndrome.
   Leko.
  Note: itch.io game page
  External Links: [Link](https://leko.itch.io/restless-wing-syndrome)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.13.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [41]
  M. Li, Z. Wang, K. He, X. Ma, and Y. Liang (2025)
  Jarvis-vla: post-training large-scale vision language models to play visual games with keyboards and mouse.
  arXiv preprint arXiv:2503.16365.
  Cited by: [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [42]
  S. Lifshitz, K. Paster, H. Chan, J. Ba, and S. McIlraith (2023)
  Steve-1: a generative model for text-to-behavior in minecraft.
  Advances in Neural Information Processing Systems 36, pp. 69900–69929.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [43]
  L. Magne, A. Awadalla, G. Wang, Y. Xu, J. Belofsky, F. Hu, J. Kim, et al. (2025)
  NitroGen: an open foundation model for generalist gaming agents.
  Note: Preprint
  Cited by: [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.12.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [44]
  G. S. Matharoo (2017)
  Rocket league 2d.
   Gurpreet Singh Matharoo.
  Note: itch.io game page
  External Links: [Link](https://matharoo.itch.io/rl2d)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.2.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [45]
  Microsoft Edge team (2020)
  Microsoft edge surf.
   Microsoft.
  Note: Built-in browser game in Microsoft Edge
  External Links: [Link](https://blogs.windows.com/msedgedev/2020/05/26/surf-game-edge-stable/)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.12.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [46]
  Microsoft (2012)
  Microsoft minesweeper.
   Microsoft.
  Note: Microsoft Store app listing
  External Links: [Link](https://apps.microsoft.com/detail/9wzdncrfhwcn)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.8.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [47]
  NAGI-P SOFT (2001)
  NS-shaft.
   NAGI-P SOFT.
  Note: Official developer download/info page
  External Links: [Link](https://www.nagi-p.com/v1/eng/nsshaft.html)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.10.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [48]
  D. Nguyen (2013)
  Flappy bird.
   .Gears.
  Note: Mobile game
  External Links: [Link](https://en.wikipedia.org/wiki/Flappy_Bird)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.2.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [49]
  OpenAI (2025)
  Computer-using agent.
  Note: <https://openai.com/index/computer-using-agent/>Accessed 2025-08-18
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.10.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [50]
  OpenAI (2025)
  GPT-5 system card.
  Note: <https://cdn.openai.com/gpt-5-system-card.pdf>System card describing the GPT-5 model family
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.7.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [51]
  D. Paglieri, B. Cupiał, S. Coward, U. Piterbarg, M. Wołczyk, A. Khan, E. Pignatelli, Ł. Kuciński, L. Pinto, R. Fergus, J. N. Foerster, J. Parker-Holder, and T. Rocktäschel (2025)
  BALROG: benchmarking agentic llm and vlm reasoning on games.
  Note: ICLR 2025
  External Links: 2411.13543
  Cited by: [§1](https://arxiv.org/html/2604.07429v1#S1.p2.1 "1 Introduction ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.11.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [52]
  A. Pajitnov (1984)
  Tetris.
   The Tetris Company.
  Note: Official history/about page
  External Links: [Link](https://tetris.com/about)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.6.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [53]
  D. Park, M. Kim, B. Choi, J. Kim, K. Lee, J. Lee, I. Park, B. Lee, J. Hwang, J. Ahn, et al. (2025)
  Orak: a foundational benchmark for training and evaluating llm agents on diverse video games.
  Note: Preprint and project release
  Cited by: [§1](https://arxiv.org/html/2604.07429v1#S1.p2.1 "1 Introduction ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.13.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [54]
  I. Pušenjak and M. Pušenjak (2009)
  Doodle jump.
   Lima Sky.
  Note: Mobile game
  External Links: [Link](https://en.wikipedia.org/wiki/Doodle_Jump)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.11.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [55]
  randomyang (2015)
  Core ball.
   randomyang.
  Note: GitHub repository (HTML5 browser game)
  External Links: [Link](https://github.com/randomyang/core-ball)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.9.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [56]
  T. Schick, J. Dwivedi-Yu, R. Dessì, R. Raileanu, M. Lomeli, L. Zettlemoyer, N. Cancedda, and T. Scialom (2023)
  Toolformer: language models can teach themselves to use tools.
  arXiv preprint arXiv:2302.04761.
  Cited by: [§2.4](https://arxiv.org/html/2604.07429v1#S2.SS4.p1.1 "2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [57]
  B. Seed (2025)
  UI-tars-1.5.
  Note: <https://seed-tars.com/1.5>
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.16.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [2nd item](https://arxiv.org/html/2604.07429v1#S4.I1.i2.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [58]
  J. Seidelin (2012)
  Wolfenstein 3d html5.
   Jacob Seidelin.
  Note: GitHub repository
  External Links: [Link](https://github.com/jseidelin/wolf3d)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.8.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [59]
  SIMA Team, A. Bolton, A. Lerchner, A. Cordell, et al. (2025)
  SIMA 2: a generalist embodied agent for virtual worlds.
  External Links: 2512.04797
  Cited by: [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [60]
  SIMA Team, M. A. Raad, A. Ahuja, C. Barros, F. Besse, A. Bolt, A. Bolton, B. Brownfield, G. Buttimore, M. Cant, et al. (2024)
  Scaling instructable agents across many simulated worlds.
  External Links: 2404.10179
  Cited by: [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [61]
  H. Sun, S. Zhang, L. Niu, L. Ren, H. Xu, H. Fu, F. Zhao, C. Yuan, and X. Wang (2025)
  Collab-overcooked: benchmarking and evaluating large language models as collaborative agents.
  External Links: 2502.20073
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [62]
  M. R. Taesiri, A. Ghildyal, S. Zadtootaghaj, N. Barman, and C. Bezemer (2025)
  VideoGameQA-bench: evaluating vision-language models for video game quality assurance.
  In NeurIPS Datasets and Benchmarks Track,
  Note: Paper reports 9 QA task types and 4,786 questions over 800+ games
  Cited by: [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.4.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [63]
  W. Tan, X. Li, Y. Fang, H. Yao, S. Yan, H. Luo, T. Ao, H. Li, H. Ren, B. Yi, et al. (2025)
  Lumine: an open recipe for building generalist agents in 3d open worlds.
  arXiv preprint arXiv:2511.08892.
  Cited by: [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [64]
  W. Tan, W. Zhang, X. Xu, H. Xia, Z. Ding, B. Li, B. Zhou, J. Yue, J. Jiang, Y. Li, et al. (2024)
  Cradle: empowering foundation agents towards general computer control.
  arXiv preprint arXiv:2403.03186.
  Cited by: [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [65]
  K. Team, Y. Bai, Y. Bao, G. Chen, J. Chen, N. Chen, R. Chen, Y. Chen, Y. Chen, Y. Chen, et al. (2025)
  Kimi k2: open agentic intelligence.
  arXiv preprint arXiv:2507.20534.
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.9.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [66]
  R. Terrell (2015)
  Astray.
   wwwtyro.
  Note: GitHub repository and GitHub Pages browser game
  External Links: [Link](https://github.com/wwwtyro/Astray)
  Cited by: [Table 4](https://arxiv.org/html/2604.07429v1#S3.T4.9.4.2.1.1 "In 3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [67]
  TinyDobbins (2022)
  Monkey mart.
   TinyDobbins.
  Note: Browser game page (Poki)
  External Links: [Link](https://poki.com/en/g/monkey-mart)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.9.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [68]
  J. Tong, J. Tang, H. Li, Y. Mou, M. Zhang, J. Zhao, Y. Wen, F. Song, J. Zhan, Y. Lu, C. Tao, Z. Guo, J. Yu, T. Cheng, Z. Xi, C. Jiang, Z. Yin, Y. Zheng, W. Ge, G. Chen, T. Gui, X. Qiu, Q. Zhang, and X. Huang (2025)
  Game-rl: synthesizing multimodal verifiable game data to boost vlms’ general reasoning.
  External Links: 2505.13886
  Cited by: [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.3.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [69]
  G. Wang, Y. Xie, Y. Jiang, A. Mandlekar, C. Xiao, Y. Zhu, L. Fan, and A. Anandkumar (2023)
  Voyager: an open-ended embodied agent with large language models.
  arXiv preprint arXiv:2305.16291.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [70]
  X. Wang, B. Zhuang, and Q. Wu (2025)
  Are large vision language models good game players?.
  External Links: 2503.02358
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [71]
  Z. Wang, S. Cai, A. Liu, Y. Jin, J. Hou, B. Zhang, H. Lin, Z. He, Z. Zheng, Y. Yang, X. Ma, and Y. Liang (2023)
  JARVIS-1: open-world multi-task agents with memory-augmented multimodal language models.
  arXiv preprint arXiv:2311.05997.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [72]
  Z. Wang, X. Li, Y. Ye, J. Fang, H. Wang, L. Liu, S. Liang, J. Lu, et al. (2025)
  Game-tars: pretrained foundation models for scalable generalist multimodal game agents.
  Note: Technical report
  Cited by: [§6.3](https://arxiv.org/html/2604.07429v1#S6.SS3.p1.1 "6.3 Game Agents and Scalable Infrastructure ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [73]
  J. Wardle (2021)
  Wordle.
   The New York Times Games.
  Note: Browser game
  External Links: [Link](https://en.wikipedia.org/wiki/Wordle)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab2.3.9.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [74]
  xAI (2024)
  Grok: xai’s multimodal reasoning model.
  Note: <https://x.ai/blog/grok>Official description of the Grok model family
  Cited by: [Table 5](https://arxiv.org/html/2604.07429v1#S3.T5.3.1.8.1 "In 3.5 Outcome-Based State-Verifiable Evaluation ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [1st item](https://arxiv.org/html/2604.07429v1#S4.I1.i1.p1.1 "In 4.1 Experiment Setup ‣ 4 Experiments ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [75]
  T. Xie, D. Zhang, J. Chen, X. Li, S. Zhao, R. Cao, T. J. Hua, Z. Cheng, D. Shin, F. Lei, Y. Liu, Y. Xu, S. Zhou, S. Savarese, C. Xiong, V. Zhong, and T. Yu (2024)
  OSWorld: benchmarking multimodal agents for open-ended tasks in real computer environments.
  External Links: 2404.07972
  Cited by: [§1](https://arxiv.org/html/2604.07429v1#S1.p2.1 "1 Introduction ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [76]
  Y. Xie, Y. Ma, S. Lan, A. Yuille, J. Xiao, and C. Wei (2025)
  Play to generalize: learning to reason through game play.
  External Links: 2506.08011
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [77]
  X. Xu, P. Bu, Y. Wang, B. F. Karlsson, Z. Wang, T. Song, Q. Zhu, J. Song, Z. Ding, and B. Zheng (2025)
  DeepPHY: benchmarking agentic vlms on physical reasoning.
  External Links: 2508.05405,
  [Link](https://arxiv.org/abs/2508.05405)
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [78]
  S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao (2022)
  ReAct: synergizing reasoning and acting in language models.
  arXiv preprint arXiv:2210.03629.
  Cited by: [§2.4](https://arxiv.org/html/2604.07429v1#S2.SS4.p1.1 "2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [79]
  A. L. Zhang, T. L. Griffiths, K. R. Narasimhan, and O. Press (2025)
  VideoGameBench: can vision-language models complete popular video games?.
  External Links: 2505.18134
  Cited by: [§1](https://arxiv.org/html/2604.07429v1#S1.p2.1 "1 Introduction ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.8.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [80]
  K. Zhang, D. Liu, Q. Zhao, J. Hou, X. Zhang, Q. Xie, M. Liu, and Y. Li (2026)
  GameVerse: can vision-language models learn from video-based reflection?.
  External Links: 2603.06656
  Cited by: [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.14.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [81]
  Z. Zhao, W. Chai, X. Wang, L. Boyi, S. Hao, S. Cao, T. Ye, J. Hwang, and G. Wang (2023)
  See and think: embodied agent in virtual environment.
  arXiv preprint arXiv:2311.15209.
  Cited by: [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [82]
  B. Zheng, B. Gou, J. Kil, H. Sun, and Y. Su (2024)
  GPT-4v(ision) is a generalist web agent, if grounded.
  In Forty-first International Conference on Machine Learning,
  External Links: [Link](https://openreview.net/forum?id=piecKJ2DlB)
  Cited by: [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [83]
  X. Zheng, L. Li, Z. Yang, P. Yu, A. J. Wang, R. Yan, Y. Yao, and L. Wang (2025)
  V-mage: a game evaluation framework for assessing vision-centric capabilities in multimodal large language models.
  arXiv preprint arXiv:2504.06148.
  Cited by: [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.10.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [84]
  X. Zheng, H. Lin, K. He, Z. Wang, Q. Fu, H. Fu, Z. Zheng, and Y. Liang (2025)
  MCU: an evaluation framework for open-ended game agents.
  In Forty-second International Conference on Machine Learning,
  Cited by: [Table 2](https://arxiv.org/html/2604.07429v1#S2.T2.6.1.6.1 "In 2.4.4 Customized Function Calling ‣ 2.4 Agent Harnesses ‣ 2 Game Agent ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents"),
  [§6.2](https://arxiv.org/html/2604.07429v1#S6.SS2.p1.1 "6.2 Video Game Benchmarks for LLM and MLLM Agents ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [85]
  Zhipu AI / Z.ai (2026)
  Minecraft clone.
   Zhipu AI / Z.ai.
  Note: Web demo (capability gallery)
  External Links: [Link](https://showcase.z.ai/)
  Cited by: [§3.3](https://arxiv.org/html/2604.07429v1#S3.SS3.tab1.3.7.2.1.1 "3.3 Game Information ‣ 3 GameWorld Benchmark ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
* [86]
  S. Zhou, F. F. Xu, H. Zhu, X. Zhou, R. Lo, A. Sridhar, X. Cheng, T. Ou, Y. Bisk, D. Fried, et al. (2023)
  Webarena: a realistic web environment for building autonomous agents.
  arXiv preprint arXiv:2307.13854.
  Cited by: [§6.1](https://arxiv.org/html/2604.07429v1#S6.SS1.p1.1 "6.1 Computer-Use Benchmarks with Online Environments ‣ 6 Related Work ‣ GameWorld: Towards Standardized and Verifiable Evaluation of Multimodal Game Agents").
