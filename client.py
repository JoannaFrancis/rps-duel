"""Interactive TCP client for a Rock-Paper-Scissors Duel."""

import argparse
import json
import socket
import sys
import threading
import time


MIN_PORT = 1024
MAX_PORT = 65535
VALID_MOVES = {"rock", "paper", "scissors"}


def valid_port(value):
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Port must be a number."
        ) from error

    if port < MIN_PORT or port > MAX_PORT:
        raise argparse.ArgumentTypeError(
            f"Port must be between {MIN_PORT} and {MAX_PORT}."
        )

    return port


def make_message(msg_type, payload=None, player_id=None):
    message = {
        "msg_type": msg_type,
        "player_id": player_id,
        "payload": payload or {},
        "timestamp": time.time(),
    }

    return (json.dumps(message) + "\n").encode("utf-8")


class RpsClient:
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.sock = None
        self.player_id = None
        self.round_number = 1
        self.can_move = False

        self.stop = threading.Event()
        self.state_lock = threading.Lock()
        self.send_lock = threading.Lock()

    def run(self):
        if not self.connect():
            return 1

        name = input("Enter your player name: ").strip()

        if not name:
            name = "Player"

        # Receive server updates in the background while the player enters moves.
        receiver = threading.Thread(
            target=self.receive_loop,
            daemon=True,
        )
        receiver.start()

        self.send_message("CONNECT", {"name": name})

        print("Type rock, paper, or scissors when it is your turn.")
        print("Type quit to leave the game.")

        try:
            while not self.stop.is_set():
                choice = input("> ").strip().lower()

                if self.stop.is_set():
                    break

                if choice == "quit":
                    self.send_message("DISCONNECT")
                    break

                if choice not in VALID_MOVES:
                    print("Please type rock, paper, scissors, or quit.")
                    continue

                with self.state_lock:
                    can_move = self.can_move
                    round_number = self.round_number

                    # Prevent a second move from being sent in the same round.
                    if can_move:
                        self.can_move = False

                if not can_move:
                    print("Wait until the server says it is your turn.")
                    continue

                self.send_message(
                    "MOVE",
                    {
                        "move": choice,
                        "round": round_number,
                    },
                )

        except (EOFError, KeyboardInterrupt):
            print("\nLeaving game.")
            self.send_message("DISCONNECT")

        finally:
            self.stop.set()
            self.close()

        return 0

    def connect(self):
        try:
            server_ip = socket.gethostbyname(self.hostname)
        except socket.gaierror:
            print(
                f"[ERROR] Unable to resolve DNS hostname "
                f"'{self.hostname}'."
            )
            print(
                "Please check your Cisco router DNS configuration "
                "('ip dns server' / 'ip host') or verify domain spelling."
            )
            return False

        try:
            self.sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM,
            )
            self.sock.connect((server_ip, self.port))

        except OSError as error:
            print(f"[ERROR] Could not connect to server: {error}")
            self.close()
            return False

        print(
            f"Connected to {self.hostname} "
            f"({server_ip}) on port {self.port}."
        )
        return True

    def send_message(self, msg_type, payload=None):
        if self.sock is None:
            return False

        try:
            with self.send_lock:
                self.sock.sendall(
                    make_message(
                        msg_type,
                        payload,
                        self.player_id,
                    )
                )
            return True

        except (BrokenPipeError, ConnectionResetError, OSError):
            print("[ERROR] Connection to the server was lost.")
            self.stop.set()
            return False

    def receive_loop(self):
        buffer = bytearray()

        while not self.stop.is_set():
            try:
                chunk = self.sock.recv(4096)
            except (ConnectionResetError, OSError):
                if not self.stop.is_set():
                    print("\n[ERROR] Connection to the server was lost.")

                self.stop.set()
                return

            if not chunk:
                if not self.stop.is_set():
                    print("\nServer closed the connection.")

                self.stop.set()
                return

            # Buffer TCP chunks until a complete JSON message arrives.
            buffer.extend(chunk)

            while True:
                newline = buffer.find(b"\n")

                if newline < 0:
                    break

                raw_message = bytes(buffer[:newline])
                del buffer[:newline + 1]

                try:
                    message = json.loads(
                        raw_message.decode("utf-8")
                    )
                except (UnicodeDecodeError, json.JSONDecodeError):
                    print("\n[ERROR] Server sent an invalid message.")
                    continue

                self.display_message(message)

    def display_message(self, message):
        msg_type = message.get("msg_type")
        payload = message.get("payload", {})

        if not isinstance(payload, dict):
            return

        # Apply the server-authoritative round and turn status locally.
        with self.state_lock:
            if "player_id" in payload:
                self.player_id = payload["player_id"]

            if "round" in payload:
                self.round_number = payload["round"]

            if "can_move" in payload:
                self.can_move = payload["can_move"]

        if msg_type == "LOBBY_WAIT":
            print(f"\n{payload.get('message', 'Waiting...')}")

        elif msg_type == "GAME_START":
            print(f"\n{payload.get('message', 'Game started.')}")
            self.print_scores(payload.get("scores", {}))

        elif msg_type == "STATE_UPDATE":
            print(f"\n{payload.get('message', '')}")

        elif msg_type == "MOVE_ACK":
            print(f"\n{payload.get('message', 'Move received.')}")

        elif msg_type == "ROUND_RESULT":
            print(f"\n{payload.get('message', 'Round complete.')}")
            print(f"Moves: {payload.get('moves', {})}")
            self.print_scores(payload.get("scores", {}))

        elif msg_type == "GAME_OVER":
            print(f"\n{payload.get('message', 'Game over.')}")
            self.print_scores(payload.get("scores", {}))
            self.stop.set()

        elif msg_type == "ERROR":
            print(
                f"\n[ERROR] "
                f"{payload.get('message', 'Unknown error.')}"
            )

    @staticmethod
    def print_scores(scores):
        if not isinstance(scores, dict):
            return

        score_parts = []

        for player in scores.values():
            if isinstance(player, dict):
                score_parts.append(
                    f"{player.get('name', 'Player')}: "
                    f"{player.get('score', 0)}"
                )

        if score_parts:
            print(f"Score — {' | '.join(score_parts)}")

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass

            self.sock = None


def main():
    parser = argparse.ArgumentParser(
        description="Rock-Paper-Scissors Duel client"
    )
    parser.add_argument(
        "-i",
        required=True,
        dest="hostname",
        help="Server hostname or IP address",
    )
    parser.add_argument(
        "-p",
        required=True,
        type=valid_port,
        metavar="PORT",
        help="Server TCP port (1024-65535).",
    )
    args = parser.parse_args()

    client = RpsClient(args.hostname, args.p)
    return client.run()


if __name__ == "__main__":
    sys.exit(main())