from fastapi import APIRouter, Depends, File, UploadFile, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
import json
import asyncio
import queue

from src.flexr.crew import Flexr
from fastapi import HTTPException
from pydantic import BaseModel
from .auth import authenticate_user, LoginRequest
from typing import Dict, Optional
import tempfile
from loguru import logger
from .db_factory import DBFactory
from .task_manager import task_manager
from crewai.tasks.task_output import TaskOutput
from .event_models import ProgressEvent

router = APIRouter(prefix="/api", tags=["AI Crews"])


class CrewInput(BaseModel):
    """
    Input model for crew operations
    """

    query: str | None = None

class FeedbackRequest(BaseModel):
    """
    Feedback request model
    """

    messageId: str
    liked: bool
    reason: Optional[str] = None
    content: str
    metadata: Optional[str] = None

class TaskCreationResponse(BaseModel):
    task_id: str

def crew_runner(task_id: str, inputs: dict):
    """Function to run the crew and handle callbacks."""
    # Create and set a new event loop for this background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    queue = task_manager.get_queue(task_id)

    def send_event(event: ProgressEvent):
        queue.put(event.to_sse_format())

    try:
        start_event = ProgressEvent(
            type="status_update",
            stage="start",
            status="Seeking the best answer",
        )
        send_event(start_event)
        
        flexr_crew_instance = Flexr()
        crew = flexr_crew_instance.crew(task_id=task_id, q=queue)
        
        result = crew.kickoff(inputs)
        
        logger.info(f"Crew for task_id {task_id} finished with result: {result}")
        end_event = ProgressEvent(
            type="status_update",
            stage="end",
            status="completed",
            message=result.raw
        )
        send_event(end_event)

    except Exception as e:
        logger.error(f"Crew execution for task_id {task_id} failed: {e}")
        error_event = ProgressEvent(
            type="error",
            stage="end",
            status="failed",
            message=f"An error occurred: {str(e)}"
        )
        send_event(error_event)
        
    finally:
        task_manager.close_task_queue(task_id)
        loop.close()


@router.post(
    "/qa",
    summary="Flexr Crew Handler",
    description="Handle knowledgebase related questions",
    response_model=TaskCreationResponse
)
async def handle_qa(input_data: CrewInput, background_tasks: BackgroundTasks):
    """
    QA team processes inquiries asynchronously and returns a task ID.
    - **input_data**: Input data containing questions
    Returns: A task ID for polling the status.
    """
    task_id = task_manager.create_task()
    background_tasks.add_task(crew_runner, task_id, input_data.model_dump())
    return {"task_id": task_id}


@router.get("/task-progress/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """
    Get the status of a task using SSE.
    """
    queue = task_manager.get_queue(task_id)

    async def event_stream():
        while True:
            if await request.is_disconnected():
                logger.info(f"Client for task {task_id} disconnected.")
                break

            try:
                data = await asyncio.to_thread(queue.get)
                if data is None:
                    break
                yield data
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue
            except Exception as e:
                logger.error(f"Error in SSE stream for task {task_id}: {e}")
                error_event = ProgressEvent(
                    type="error",
                    stage="end",
                    status="failed",
                    message="An error occurred while streaming."
                )
                yield error_event.to_sse_format()
                break
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post(
    "/login", summary="User Authentication", description="Authenticate user credentials"
)
async def login(request: LoginRequest):
    """
    Process user login requests

    - **request**: Login request containing username and password

    Returns: Authentication result
    """
    return authenticate_user(request)


@router.post(
    "/upload",
    summary="File upload",
    description="Handle file uploads then return the file path",
)
async def upload(file: UploadFile = File(...)):
    """
    Process file uploads

    - **file**: Uploaded file

    Returns: File path
    """
    logger.info(f"file: {file}")

    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=file.filename
        ) as temp_file:
            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)
            temp_file_path = temp_file.name
            logger.info(f"temp_file_path: {temp_file_path}")
            return {"url": temp_file_path, "status": "success", "name": temp_file_path}
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        await file.close()


@router.post(
    "/feedback",
    summary="feedback crewai response",
    description="feedback crewai response",
)
def log_feedback(feedback: FeedbackRequest):
    """
    Log feedback for crewai response and save to SQLite database

    Args:
        feedback (FeedbackRequest): The feedback data to be logged

    Returns:
        dict: Status of the feedback logging operation
    """
    logger.info(f"feedback: {feedback}")
    db_util = DBFactory.get_db_util()
    return db_util.save_feedback(feedback)
