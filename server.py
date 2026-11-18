"""Selector-based TCP server for a two-player Rock-Paper-Scissors Duel."""

import argparse
import json
import selectors
import socket
import sys
import time
from dataclasses import dataclass, field


MIN_PORT = 1024
MAX_PORT = 65535
WINNING_SCORE = 3
VALID_MOVES = {"rock", "paper", "scissors"}
BEATS = {
    "rock": "scissors",
    "paper": "rock",
    "scissors": "paper",
}


def valid_port(value):
    port = int(value)

    if port < MIN_PORT or port > MAX_PORT:
        raise argparse.ArgumentTypeError(
            f"Port must be between {MIN_PORT} and {MAX_PORT}."
        )

    return port


# Encode one JSON message per newline-delimited TCP frame.
def make_message(msg_type, payload=None, player_id=None):
    message = {
        "msg_type": msg_type,
        "player_id": player_id,
        "payload": payload or {},
        "timestamp": time.time(),
    }

    return (json.dumps(message) + "\n").encode("utf-8")


@dataclass
class Client:
    sock: socket.socket
    address: tuple
    read_buffer: bytearray = field(default_factory=bytearray)
    write_buffer: bytearray = field(default_factory=bytearray)
    player_id: int = None
    name: str = ""


# The server is authoritative for all round and score state.
class RpsServer:
    def __init__(self, port):
        self.port = port
        self.selector = selectors.DefaultSelector()
        self.listener = None
        self.clients = {}
        self.players = []
        self.state = "WAITING_FOR_PLAYERS"
        self.round_number = 1
        self.moves = {}
        self.scores = {1: 0, 2: 0}
        self.match_finished = False

    def run(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("0.0.0.0", self.port))
        self.listener.listen()
        self.listener.setblocking(False)

        self.selector.register(
            self.listener,
            selectors.EVENT_READ,
            data=None,
        )

        print(f"Server listening on 0.0.0.0:{self.port}")
        print("Waiting for two players. Press Ctrl+C to stop.")

        try:
            while True:
                # A selector lets one event loop serve both clients
                # without blocking.
                events = self.selector.select(timeout=1)

                for key, mask in events:
                    if key.data is None:
                        self.accept_client()
                    else:
                        self.service_client(key.data, mask)

        except KeyboardInterrupt:
            print("\nServer stopped.")

        finally:
            self.close()

    def accept_client(self):
        client_sock, address = self.listener.accept()
        client_sock.setblocking(False)

        if len(self.clients) >= 2 or self.match_finished:
            try:
                client_sock.sendall(
                    make_message(
                        "ERROR",
                        {"message": "This two-player game is full."},
                    )
                )
            except OSError:
                pass

            client_sock.close()
            return

        client = Client(client_sock, address)
        self.clients[client_sock] = client

        self.selector.register(
            client_sock,
            selectors.EVENT_READ,
            data=client,
        )

        print(f"TCP connection from {address[0]}:{address[1]}")

    def service_client(self, client, mask):
        if mask & selectors.EVENT_READ:
            self.read_client(client)

        if client.sock not in self.clients:
            return

        if mask & selectors.EVENT_WRITE:
            self.write_client(client)

    def read_client(self, client):
        try:
            chunk = client.sock.recv(4096)
        except (ConnectionResetError, OSError) as error:
            self.remove_client(client, f"Read error: {error}")
            return

        # An empty recv means the client closed its TCP connection.
        if not chunk:
            self.remove_client(client, "Client disconnected")
            return

        # TCP is a byte stream, so buffer chunks until a full JSON frame arrives.
        client.read_buffer.extend(chunk)

        while True:
            newline = client.read_buffer.find(b"\n")

            if newline < 0:
                return

            raw_message = bytes(client.read_buffer[:newline])
            del client.read_buffer[:newline + 1]

            if not raw_message:
                continue

            try:
                message = json.loads(raw_message.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_error(
                    client,
                    "Messages must contain valid UTF-8 JSON.",
                )
                continue

            if not isinstance(message, dict):
                self.send_error(client, "Message must be a JSON object.")
                continue

            self.handle_message(client, message)

            if client.sock not in self.clients:
                return

    def write_client(self, client):
        try:
            sent = client.sock.send(client.write_buffer)
        except (BrokenPipeError, ConnectionResetError, OSError) as error:
            self.remove_client(client, f"Write error: {error}")
            return

        del client.write_buffer[:sent]
        self.update_selector_events(client)

    def handle_message(self, client, message):
        msg_type = message.get("msg_type")
        payload = message.get("payload", {})

        if msg_type == "CONNECT":
            self.connect_player(client, payload)

        elif msg_type == "MOVE":
            self.record_move(client, payload)

        elif msg_type == "DISCONNECT":
            self.remove_client(client, "Client quit")

        else:
            self.send_error(client, "Unknown message type.")

    def connect_player(self, client, payload):
        if client.player_id is not None:
            self.send_error(client, "You already joined the game.")
            return

        if not isinstance(payload, dict):
            self.send_error(client, "CONNECT payload must be an object.")
            return

        name = payload.get("name", "")

        if not isinstance(name, str):
            self.send_error(client, "Player name must be text.")
            return

        client.player_id = len(self.players) + 1
        client.name = name.strip()[:24]

        if not client.name:
            client.name = f"Player {client.player_id}"

        self.players.append(client)

        self.queue_message(
            client,
            "STATE_UPDATE",
            {
                "message": f"Joined as {client.name}.",
                "player_id": client.player_id,
                "round": self.round_number,
                "can_move": False,
            },
        )

        if len(self.players) == 1:
            self.state = "LOBBY_WAIT"

            self.queue_message(
                client,
                "LOBBY_WAIT",
                {"message": "Waiting for Player 2..."},
            )
            return

        self.start_game()

    def start_game(self):
        self.state = "WAITING_FOR_MOVES"
        self.round_number = 1
        self.moves.clear()
        self.scores = {1: 0, 2: 0}

        self.broadcast(
            "GAME_START",
            {
                "message": "Both players joined. First to 3 wins.",
                "round": self.round_number,
                "scores": self.score_summary(),
            },
        )

        self.broadcast(
            "STATE_UPDATE",
            {
                "message": "Round 1: choose rock, paper, or scissors.",
                "round": self.round_number,
                "can_move": True,
                "scores": self.score_summary(),
            },
        )

    def record_move(self, client, payload):
        if client.player_id is None:
            self.send_error(client, "Send CONNECT before MOVE.")
            return

        if self.state != "WAITING_FOR_MOVES":
            self.send_error(client, "Moves are not allowed right now.")
            return

        if not isinstance(payload, dict):
            self.send_error(client, "MOVE payload must be an object.")
            return

        move = payload.get("move", "")

        if not isinstance(move, str) or move.lower() not in VALID_MOVES:
            self.send_error(
                client,
                "Your move must be rock, paper, or scissors.",
            )
            return

        if payload.get("round") not in (None, self.round_number):
            self.send_error(client, "That move belongs to another round.")
            return

        if client.player_id in self.moves:
            self.send_error(client, "Only one move is allowed per round.")
            return

        self.moves[client.player_id] = move.lower()

        self.queue_message(
            client,
            "MOVE_ACK",
            {
                "message": "Move received. Waiting for the other player."
            },
        )

        # Keep moves hidden until both players have submitted one.
        if len(self.moves) < 2:
            self.queue_message(
                client,
                "STATE_UPDATE",
                {
                    "message": "Waiting for the other player's move...",
                    "round": self.round_number,
                    "can_move": False,
                    "scores": self.score_summary(),
                },
            )
            return

        # Both moves are present, so the server resolves the round.
        self.evaluate_round()

    def evaluate_round(self):
        player_one, player_two = self.players

        move_one = self.moves[player_one.player_id]
        move_two = self.moves[player_two.player_id]
        winner_id = None

        if move_one != move_two:
            if BEATS[move_one] == move_two:
                winner_id = player_one.player_id
            else:
                winner_id = player_two.player_id

            self.scores[winner_id] += 1

        if winner_id is None:
            result = f"Round {self.round_number} is a tie."
        else:
            winner = self.player_for_id(winner_id)
            result = f"{winner.name} wins round {self.round_number}."

        self.broadcast(
            "ROUND_RESULT",
            {
                "round": self.round_number,
                "moves": {
                    str(player_one.player_id): move_one,
                    str(player_two.player_id): move_two,
                },
                "winner_id": winner_id,
                "message": result,
                "scores": self.score_summary(),
            },
        )

        if winner_id and self.scores[winner_id] == WINNING_SCORE:
            winner = self.player_for_id(winner_id)

            self.match_finished = True
            self.state = "CLEANUP"

            self.broadcast(
                "GAME_OVER",
                {
                    "message": f"{winner.name} wins the match!",
                    "winner_id": winner_id,
                    "scores": self.score_summary(),
                },
            )
            return

        self.moves.clear()
        self.round_number += 1

        self.broadcast(
            "STATE_UPDATE",
            {
                "message": (
                    f"Round {self.round_number}: "
                    "choose rock, paper, or scissors."
                ),
                "round": self.round_number,
                "can_move": True,
                "scores": self.score_summary(),
            },
        )

    def remove_client(self, client, reason):
        if client.sock not in self.clients:
            return

        opponents = [
            player for player in self.players
            if player is not client
        ]

        game_active = (
            self.state == "WAITING_FOR_MOVES"
            and not self.match_finished
        )

        # A disconnect during an active game counts as a forfeit.
        if client.player_id is not None and opponents and game_active:
            winner = opponents[0]

            self.match_finished = True
            self.state = "CLEANUP"

            self.queue_message(
                winner,
                "GAME_OVER",
                {
                    "message": (
                        f"{client.name} disconnected. "
                        "You win by forfeit."
                    ),
                    "winner_id": winner.player_id,
                    "scores": self.score_summary(),
                },
            )

        try:
            self.selector.unregister(client.sock)
        except (KeyError, ValueError):
            pass

        self.clients.pop(client.sock, None)

        if client in self.players:
            self.players.remove(client)

        try:
            client.sock.close()
        except OSError:
            pass

        print(f"Client {client.address} disconnected: {reason}")

        if not self.clients:
            self.reset_game()

    def reset_game(self):
        self.players.clear()
        self.moves.clear()
        self.scores = {1: 0, 2: 0}
        self.round_number = 1
        self.match_finished = False
        self.state = "WAITING_FOR_PLAYERS"

        print("Ready for two new players.")

    def queue_message(self, client, msg_type, payload=None):
        if client.sock not in self.clients:
            return

        client.write_buffer.extend(
            make_message(msg_type, payload, client.player_id)
        )

        self.update_selector_events(client)

    def broadcast(self, msg_type, payload):
        for client in list(self.players):
            self.queue_message(client, msg_type, payload)

    def send_error(self, client, message):
        self.queue_message(
            client,
            "ERROR",
            {"message": message},
        )

    def update_selector_events(self, client):
        if client.sock not in self.clients:
            return

        events = selectors.EVENT_READ

        if client.write_buffer:
            events |= selectors.EVENT_WRITE

        self.selector.modify(
            client.sock,
            events,
            data=client,
        )

    def player_for_id(self, player_id):
        for player in self.players:
            if player.player_id == player_id:
                return player

        return None

    def score_summary(self):
        return {
            str(player.player_id): {
                "name": player.name,
                "score": self.scores.get(player.player_id, 0),
            }
            for player in self.players
        }

    def close(self):
        for client in list(self.clients.values()):
            self.remove_client(client, "Server shutdown")

        if self.listener is not None:
            try:
                self.selector.unregister(self.listener)
            except (KeyError, ValueError):
                pass

            self.listener.close()

        self.selector.close()


def main():
    parser = argparse.ArgumentParser(
        description="Rock-Paper-Scissors Duel server"
    )
    parser.add_argument(
        "-p",
        required=True,
        type=valid_port,
        metavar="PORT",
        help="Listening TCP port (1024-65535).",
    )
    args = parser.parse_args()

    try:
        server = RpsServer(args.p)
        server.run()
    except OSError as error:
        print(f"[ERROR] Could not start server: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())