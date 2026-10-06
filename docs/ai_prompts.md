#Rock-Paper-Scissors AI prompts

**Course:** CS 457 - Computer Netwsorks and the Internet
**Student:** Joanna Welch
**Game:** Rock-Paper-Scissors Duel
**Sprint:** Sprint 1 - AI Prompt Strategy

---
## 1. AI Constraints
 How I Will Constrain AI

When I use AI to help with implementation, I will give it specific instructions based on my project design. The generated code should:

- Use Python 3.
- Use the standard Python `socket` library.
- Use TCP connections.
- Use newline-delimited JSON messages.
- Follow the message schemas from `protocol_blueprint.md`.
- Follow the server states from `fsm_specification.md`.
- Keep the server responsible for validating moves, tracking score, and deciding the match winner.
- Use `ERROR` messages for invalid moves, malformed messages, duplicate moves, or wrong-round moves.
- Handle `DISCONNECT`, closed sockets, and unexpected connection loss without crashing the server.

---

## 2. Prompt for Protocol Helper 

Generate Python helper functions for sending and receiving messages using newline-delimited JSON.

Use these rules:
- Each message is one JSON object.
- Each message is encoded as UTF-8.
- Each message ends with a newline character \n.
- The receiver must buffer incoming data and split complete messages on newline characters.
- Do not assume that one recv() call contains one complete message.
- Do not invent new message types or fields.

The only valid message types are:
CONNECT, LOBBY_WAIT, GAME_START, MOVE, MOVE_ACK, STATE_UPDATE, GAME_OVER, ERROR, and DISCONNECT.