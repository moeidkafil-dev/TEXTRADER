# Original Architecture Inventory

## Source
`trader_final_architecture.graphml`

## Extracted node/group terminology
The following labels were extracted from the supplied GraphML. They are preserved as source terminology:

- `data reader`
- `Folder 1`
- `context maker`
- `context sender`
- `memory / database`
- `Folder 2`
- `database`
- `memory`
- `agent 1`
- `Folder 3`
- `llm`
- `context compiler`
- `decision system`
- `planner`
- `schduler`
- `tool manager`
- `tool executer`
- `hidden memory`
- `Observability`
- `agent 2`
- `Folder 4`
- `agent 3`
- `Folder 5`
- `final tools`
- `Folder 6`
- `sell system`
- `buy system`
- `skip`
- `Folder 31`
- `memory architecture`
- `Folder 13`
- `Sensory Memory`
- `Working Memory`
- `Short-Term Memory (STM)`
- `Long-Term Memory (LTM)`
- `Episodic Memory`
- `Semantic (Knowledge) Memory`
- `Procedural Memory`
- `Goal Memory`
- `Task Memory`
- `Context Memory`
- `Conversation Memory`
- `Tool Memory`
- `Environment / World State`
- `User Profile Memory`
- `Learning Memory`
- `Experience Memory`
- `Failure Memory`
- `Success Memory`
- `Reflection Memory`
- `Planning Memory`
- `RAG Memory`
- `Cache Memory`
- `Shared Memory`
- `Agent Local Memory`
- `Audit / History Memory`
- `Temporal Memory`
- `Meta Memory`
- `memory manager agent`
- `memory manager`
- `Folder 26`
- `input reader`
- `input analyser`
- `input setter in memory`
- `memory analyser`
- `memory complite analyser`
- `finde junks`
- `tables cleaner`
- `being in sleep mode`
- `output request analyser`
- `result maker`
- `result/log`
- `DB manager agent architecture`
- `Folder 18`
- `massgaes reciver`
- `massages compile`
- `massages reader`
- `massages analyser`
- `executer`
- `DB analyser`
- `DB Situation analyser`
- `DB log maker`
- `log maker`
- `result sender`
- `log sender`
- `message system`
- `Folder 11`
- `user`s emaile`
- `user`s telegram`
- `email sender`
- `telegram message
 sender`
- `message maker`
- `message send 
manager`
- `message reciver`
- `message analyser`
- `sender to agent`
- `DECISION ENGINE`
- `Folder 12`
- `DECISION VALIDATOR`
- `RISK ENGINE`
- `EXECUTION GUARD`
- `BROKER / EXCHANGE`
- `Risk Engine`
- `Position Size`
- `Max Daily Loss`
- `Max Drawdown`
- `Exposure Limit`
- `Leverage Limit`
- `Stop Loss Validation`
- `Take Profit Validation`
- `Correlation Exposure`
- `Portfolio Exposure`
- `Trading Session Rules`
- `Emergency Kill Switch`

## Reading rule
The GraphML contains grouped nodes, nested graphs, visual metadata and directed edges. A label alone does not prove an implementation requirement; its role must be interpreted together with its incoming/outgoing edges and group membership.

## Architectural interpretation
The source architecture appears to organize the system around:
1. data acquisition/reading;
2. context construction;
3. memory/database;
4. agent/model orchestration;
5. decision-making;
6. validation;
7. risk and execution;
8. monitoring/history.

The implementation PRD therefore treats these as architectural concerns while preserving the original design as the authoritative visual source.

## Fidelity requirement
During implementation, every source node must be mapped to one of:
- concrete module;
- service;
- interface/port;
- data model;
- policy;
- runtime component;
- test fixture;
- observability artifact.

No source node may silently disappear from the implementation backlog.
