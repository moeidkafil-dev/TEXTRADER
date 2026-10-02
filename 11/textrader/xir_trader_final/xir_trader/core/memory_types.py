"""
The 28 memory types, preserved verbatim and in the original order from
05_AGENT_AND_MEMORY_MODEL/AGENT_AND_MEMORY_MODEL.md.

Per OI-06 these form a *catalog*, not a mandatory sequential pipeline —
"memory manager agent" is the entry point. Nothing here may be removed
or merged (SUPER_PROMPT.md absolute prohibition #1).
"""
from enum import Enum


class MemoryType(str, Enum):
    SENSORY = "sensory_memory"                    # 1
    WORKING = "working_memory"                     # 2
    SHORT_TERM = "short_term_memory"                # 3 (STM)
    LONG_TERM = "long_term_memory"                  # 4 (LTM)
    EPISODIC = "episodic_memory"                    # 5
    SEMANTIC = "semantic_knowledge_memory"          # 6
    PROCEDURAL = "procedural_memory"                # 7
    GOAL = "goal_memory"                            # 8
    TASK = "task_memory"                            # 9
    CONTEXT = "context_memory"                      # 10
    CONVERSATION = "conversation_memory"            # 11
    TOOL = "tool_memory"                            # 12
    ENVIRONMENT = "environment_world_state"         # 13
    USER_PROFILE = "user_profile_memory"            # 14
    LEARNING = "learning_memory"                    # 15
    EXPERIENCE = "experience_memory"                # 16
    FAILURE = "failure_memory"                      # 17
    SUCCESS = "success_memory"                      # 18
    REFLECTION = "reflection_memory"                # 19
    PLANNING = "planning_memory"                    # 20
    RAG = "rag_memory"                              # 21
    CACHE = "cache_memory"                          # 22
    SHARED = "shared_memory"                        # 23
    AGENT_LOCAL = "agent_local_memory"              # 24
    AUDIT_HISTORY = "audit_history_memory"          # 25 (append-only, I4)
    TEMPORAL = "temporal_memory"                    # 26
    META = "meta_memory"                            # 27
    MEMORY_MANAGER_AGENT = "memory_manager_agent"   # 28 — entry point (OI-06)


ORDERED_MEMORY_TYPES = list(MemoryType)
assert len(ORDERED_MEMORY_TYPES) == 28, "The 28 memory types must never be removed or merged."
