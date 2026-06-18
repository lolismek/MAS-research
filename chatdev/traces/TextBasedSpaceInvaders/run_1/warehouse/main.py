'''
Entry point for the simplified Space Invaders game.
'''
def main():
    '''Create and run the game.'''
    try:
        from game import Game
    except ModuleNotFoundError as exc:
        if exc.name == "pygame":
            raise SystemExit(
                "pygame is required to run this game. Please install it with: pip install pygame"
            ) from exc
        raise
    game = Game()
    game.run()
if __name__ == "__main__":
    main()