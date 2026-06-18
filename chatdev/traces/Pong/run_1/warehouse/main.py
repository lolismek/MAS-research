'''
Entry point for the two-player Pong game.
Provides a clear startup message if pygame is missing.
'''
try:
    from game import PongGame
except ImportError as e:
    raise SystemExit(
        "Failed to import game modules. Make sure dependencies are installed: pip install -r requirements.txt"
    ) from e
def main():
    try:
        game = PongGame()
        game.run()
    except Exception as e:
        print(f"Failed to start game: {e}")
        raise
if __name__ == "__main__":
    main()