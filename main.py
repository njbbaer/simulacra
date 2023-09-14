import argparse

from src.cli_interface import ChatInterface

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('context', type=str)
    args = parser.parse_args()

    interface = ChatInterface(args.context)
    interface.run()
