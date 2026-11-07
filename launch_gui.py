"""Desktop application entry point."""
import argparse


def main():
    parser = argparse.ArgumentParser(description="CourseFlow")
    parser.add_argument("--file")
    args = parser.parse_args()
    from courseflow.gui import main as run_gui
    run_gui(args.file)


if __name__ == "__main__":
    main()
