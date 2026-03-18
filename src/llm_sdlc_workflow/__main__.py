"""Allows running the pipeline as: python -m llm_sdlc_workflow"""
import sys

from llm_sdlc_workflow.main_entry import main

if __name__ == "__main__":
    sys.exit(main())
