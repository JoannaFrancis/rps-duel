#Rock-Paper-Scissors Duel Protocol Blueprint

**Course:** CS 457 - Computer Networks and the Internet
**Student:** Joanna Welch
**Game:** Rock-Paper-Scissors Duel
**Sprint:** Sprint 1 - Application Protocol Design

---
## 2. Application-Layer Messaging Protocol Blueprint (Sprint 1 Deliverable)

### 2.1 Message Transport & Serialization Format
- **Transport Protocol:** TCP
- **Serialization Format:** JSON 
- **Framing Mechanism:** Newline-delimited (`\n`) JSON payloads 

Rock-Paper-Scissor Duel uses newline-delimited JSON. Each application-layer message is serialized as one compact JSON object, encoded as UTF-8, and terminated with a newline charachter `\n`. The newline char is not part of the object itself but added after the JSON object when sent over the socket. 

### 2.2 Message Schema Definitions

#### Message Types:
1. `CONNECT` 
**Direction:** (Client -> Server)
**Purpose:** Request to join the game room.
**Schema:** 
```json
{
    "msg_type": "CONNECT",
    "player_alias":  "Alice",
    "timestamp": 1727000000
}
```
2. `LOBBY_WAIT` 
**Direction:** (Server -> Client)
**Purpose:**2. Server tells the first connected client that it is waiting for a second player to join the game.  
**Schema:**
```json 
{
  "msg_type": "LOBBY_WAIT",
  "sender": "SERVER",
  "payload": {
    "assigned_player_id": "Player_1",
    "message": "Waiting for Player_2 to connect."
  },
  "timestamp": 1727000001
}
```

3. `GAME_START` : 
**Direction:** (Server -> Clients)
**Purpose:** Both players are notified that the game has started and player roles are confirmed. 
**Schema For Player_1:** 
```json
{
  "msg_type": "GAME_START",
  "sender": "SERVER",
  "payload": {
    "round": 1,
    "players": {
      "Player_1": "Alice",
      "Player_2": "Bob"
    },
    "your_player_id": "Player_1",
    "score": {
      "Player_1": 0,
      "Player_2": 0
    },
    "message": "Game started. You are Player_1. Submit ROCK, PAPER, or SCISSORS."
  },
  "timestamp": 1727000002
}
```
**Schema For Player_2:** 
```json
{
  "msg_type": "GAME_START",
  "sender": "SERVER",
  "payload": {
    "round": 1,
    "players": {
      "Player_1": "Alice",
      "Player_2": "Bob"
    },
    "your_player_id": "Player_2",
    "score": {
      "Player_1": 0,
      "Player_2": 0
    },
    "message": "Game started. You are Player_2. Submit ROCK, PAPER, or SCISSORS."
  },
  "timestamp": 1727000002
}
```

4. `MOVE` 
The server accepts a MOVE only if the move is ROCK, PAPER, or SCISSORS, the round number matches the current round, and the player has not already moved this round. Otherwise, the server sends ERROR.

**Direction:** (Client -> Server)
**Purpose:** Player submits one move for current round (Rock, Paper, or Scissor)
**Schema:** 
```json
{
  "msg_type": "MOVE",
  "player_id": "Player_1",
  "payload": {
    "round": 1,
    "move": "ROCK"
  },
  "timestamp": 1727000005
}
```
5. `MOVE_ACK`
**Direction:** (Server -> Client)
**Purpose:** Server confirms that player's move was received and that they are waiting for the other player to submit. 
**Schema:** 
```json
{
  "msg_type": "MOVE_ACK",
  "sender": "SERVER",
  "payload": {
    "round": 1,
    "message": "Move received. Waiting for opponent."
  },
  "timestamp": 1727000006
}
```
6. `STATE_UPDATE` 
The server sends STATE_UPDATE after both valid moves have been received and the round has been evaluated.

**Direction:** (Server -> Clients)
**Purpose:** Server broadcasts the round results and updated score after both moves are recieved.
**Schema for win:** 
```json
{
  "msg_type": "STATE_UPDATE",
  "sender": "SERVER",
  "payload": {
    "round": 1,
    "moves": {
      "Player_1": "ROCK",
      "Player_2": "SCISSORS"
    },
    "round_winner": "Player_1",
    "score": {
      "Player_1": 1,
      "Player_2": 0
    },
    "next_round": 2,
    "message": "Player_1 wins the round."
  },
  "timestamp": 1727000008
}
```
**Schema for draw:** 
```json
{
  "msg_type": "STATE_UPDATE",
  "sender": "SERVER",
  "payload": {
    "round": 1,
    "moves": {
      "Player_1": "ROCK",
      "Player_2": "ROCK"
    },
    "round_winner": "DRAW",
    "score": {
      "Player_1": 0,
      "Player_2": 0
    },
    "next_round": 2,
    "message": "Round tied. No points awarded."
  },
  "timestamp": 1727000008
}
```

7. `GAME_OVER` 
 The server sends GAME_OVER when a player reaches three round wins or when a player disconnects and forfeits.
 
**Direction:** (Server -> Clients)
**Purpose:** Server announces final match results
**Schema (standard win):** 
```json
{
  "msg_type": "GAME_OVER",
  "sender": "SERVER",
  "payload": {
    "winner": "Player_1",
    "reason": "Player_1 reached 3 round wins.",
    "final_score": {
      "Player_1": 3,
      "Player_2": 1
    }
  },
  "timestamp": 1727000020
}
```
**Schema (forfeit):** 
```json
{
  "msg_type": "GAME_OVER",
  "sender": "SERVER",
  "payload": {
    "winner": "Player_2",
    "reason": "Player_1 quit. Player_2 wins by forfeit.",
    "final_score": {
      "Player_1": 1,
      "Player_2": 2
    }
  },
  "timestamp": 1727000020
}
```
8. `ERROR` : Invalid move or malformed packet error.
**Direction:** (Server -> Client)
**Purpose:** Server rejcets and invalid, malformed, duplicate, or out of state message. 
**Schema:** 
```json
{
  "msg_type": "ERROR",
  "sender": "SERVER",
  "payload": {
    "error_code": "INVALID_MOVE",
    "message": "Move must be ROCK, PAPER, or SCISSORS."
  },
  "timestamp": 1727000009
}
```
9. `DISCONNECT` 
**Direction:** (Client -> Server)
**Purpose:** Client exits the game before completion. 
**Schema:** 
```json
{
  "msg_type": "DISCONNECT",
  "player_id": "Player_1",
  "payload": {
    "reason": "Player quit."
  },
  "timestamp": 1727000010
}
```
---
