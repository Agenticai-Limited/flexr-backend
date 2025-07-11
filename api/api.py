from fastapi import APIRouter, Depends, File, UploadFile, BackgroundTasks, Request, Form, HTTPException, status
from fastapi.responses import StreamingResponse
import json
import asyncio
import queue

from src.flexr.main import run_with_input
from fastapi import HTTPException
from pydantic import BaseModel
from .models import Token, TokenData
from .security import get_current_user, create_access_token
from .pg_dbutil import PGDBUtil
from typing import Dict, Optional
import tempfile
from loguru import logger
from .task_manager import task_manager
from crewai.tasks.task_output import TaskOutput
from .event_models import ProgressEvent
from datetime import timedelta
from src.flexr.main import run_with_input # Import the synchronous run_with_input

router = APIRouter(prefix="/api", tags=["AI Crews"])

class CrewInput(BaseModel):
    """
    Input model for crew operations
    """
    query: str | None = None
    task_id: Optional[str] = None
    refined: bool = False

class FeedbackRequest(BaseModel):
    """
    Feedback request model
    """

    messageId: str
    liked: bool
    reason: Optional[str] = None

class TaskCreationResponse(BaseModel):
    message_id: str

class SuccessResponse(BaseModel):
    status: str = "success"

# Define a consistent success response format
def success_response(data):
    return {
        "success": True,
        "data": data
    }

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str

def crew_runner(task_id: str, input: dict):
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
        
        # Call the synchronous run_with_input from main.py
        final_state = run_with_input(input=input, task_id=task_id, q=queue, username='test') #TODO use username from request
        
        if final_state.refined_query:
        
            logger.info(f"Crew for task_id {task_id} finished with result: {final_state.refined_query}")

            # PGDBUtil.save_qa_log(task_id, input['query'], result_raw)
            
            end_event = ProgressEvent(
                type="status_update",
                stage="refined",
                status="completed",
                message={"task_id": task_id, "query": final_state.refined_query, "refined": True,}
            )
        elif final_state.qa_crew_response:
            end_event = ProgressEvent(
                type="status_update",
                stage="end",
                status="completed",
                message={"response": final_state.qa_crew_response.raw}
            )
        send_event(end_event)

    except Exception as e:
        logger.exception(f"Crew execution for task_id {task_id} failed")
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
async def handle_qa(input_data: CrewInput, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
    """
    QA team processes inquiries asynchronously and returns a task ID.
    - **input_data**: Input data containing questions
    Returns: A task ID for polling the status.
    """
    import uuid
    task_id = input_data.task_id if input_data.task_id else str(uuid.uuid4())
    task_id = task_manager.create_task(task_id)
    background_tasks.add_task(crew_runner, task_id, input_data.model_dump())
    return TaskCreationResponse(message_id=task_id)


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


@router.get("/me")
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get current user information endpoint
    Returns user info if token is valid, 401 if not
    """
    return success_response({
        "username": current_user.username,
        "is_authenticated": True
    })

@router.post("/logout")
async def logout(current_user: TokenData = Depends(get_current_user)):
    """
    Logout endpoint
    This endpoint mainly serves as a way for the client to validate their logout action
    The actual token invalidation should be handled by the client by removing the token
    """
    return success_response({
        "message": "Successfully logged out",
        "username": current_user.username
    })

@router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    """
    Login endpoint for user authentication
    """
    logger.debug(f"Login attempt for user: {username}")
    
    is_authenticated = PGDBUtil.authenticate_user(username, password)
    if not is_authenticated:
        logger.warning(f"Authentication failed for user: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )
    logger.info(f"User successfully logged in: {username}")
    return success_response({
        "access_token": access_token,
        "token_type": "bearer"
    })

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
def log_feedback(feedback: FeedbackRequest,current_user: TokenData = Depends(get_current_user)):
    """
    Log feedback for crewai response and save to SQLite database

    Args:
        feedback (FeedbackRequest): The feedback data to be logged

    Returns:
        dict: Status of the feedback logging operation
    """
    logger.info(f"feedback: {feedback}")
    try:
        PGDBUtil.save_feedback(feedback)
        return SuccessResponse()
    except Exception as e:
        logger.exception(f"Error saving feedback: {e}")
        return ErrorResponse(message=str(e))
