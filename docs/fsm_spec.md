#Rock-Paper-Scissors Duel Game Finite State Machine Design

**Course:** CS 457 - Computer Netwsorks and the Internet
**Student:** Joanna Welch
**Game:** Rock-Paper-Scissors Duel
**Sprint:** Sprint 1 - Finite State Machine Design

---
### 2.3 Game State Machine (FSM) Design (Sprint 1 Deliverable)

```mermaid
stateDiagram-v2
    [*] --> INIT
    INIT --> WAITING_FOR_PLAYERS: server starts
    WAITING_FOR_PLAYERS --> LOBBY_WAIT: Player_1 connects
    LOBBY_WAIT --> GAME_START: Player_2 connects
    GAME_START --> WAITING_FOR_MOVES: round 1 begins

    WAITING_FOR_MOVES --> WAITING_FOR_MOVES: invalid move, malformed message, duplicate move, or wrong round
    WAITING_FOR_MOVES --> EVALUATE_ROUND: both valid moves received
    WAITING_FOR_MOVES --> GAME_OVER: disconnect or forfeit

    EVALUATE_ROUND --> BROADCAST_RESULT: winner or draw determined
    BROADCAST_RESULT --> CHECK_MATCH_WIN: STATE_UPDATE sent
    CHECK_MATCH_WIN --> WAITING_FOR_MOVES: no player has 3 wins
    CHECK_MATCH_WIN --> GAME_OVER: player reaches 3 wins

    GAME_OVER --> CLEANUP: final result sent
    CLEANUP --> [*]: cleanup complete
    ```

When the server receives an invalid move, malformed message, duplicate move, or move for the wrong round, it sends an `ERROR` message and remains in `WAITING_FOR_MOVES`.

If a client sends `DISCONNECT`, closes the socket, or loses connection unexpectedly during an active match, the server treats the event as a forfeit. The opponent wins, the server sends `GAME_OVER` when possible, and the state machine transitions to `CLEANUP`.