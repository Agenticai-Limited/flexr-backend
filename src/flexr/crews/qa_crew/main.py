#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from flexr.crews.qa_crew.qa_crew import Flexr

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information


def run():
    from src.flexr.utils.milvus_util import MilvusUtil
    from src.flexr.utils.pdf_file_util import PdfFileUtil

    """
    Load the crew.
    """
    try:
        docs = PdfFileUtil().extract_documents_from(
            "NZFC Customer Services Procedures & Policies 19Jun2025.pdf"
        )
        milvus = MilvusUtil()
        milvus.save(docs)
    except Exception as e:
        e.print_exc()
        print(f"An error occurred while loading the crew: {e}")


def run1():
    """
    Run the crew.
    """
    inputs = {
        "query": "What should I do when I lost my flexr card?",
    }

    try:
        Flexr().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {"topic": "AI LLMs", "current_year": str(datetime.now().year)}
    try:
        Flexr().crew().train(
            n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs
        )

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        Flexr().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test1():
    """
    Test the crew execution and returns the results.
    """
    inputs = {"topic": "AI LLMs", "current_year": str(datetime.now().year)}

    try:
        Flexr().crew().test(
            n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs
        )

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


