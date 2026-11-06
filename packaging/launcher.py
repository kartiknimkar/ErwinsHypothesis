"""Entry point for the packaged app (see ErwinsHypothesis.spec)."""
import multiprocessing

from app.desktop import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
