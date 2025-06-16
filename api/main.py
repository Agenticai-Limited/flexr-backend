from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as ResponseValidationError
import traceback
from .logging_config import setup_logging
setup_logging()

from loguru import logger


from .api import router

app = FastAPI(
    title="Agent API",
    description="API Docs",
    version="1.0.0",
    docs_url="/docs", 
    redoc_url="/redoc"  
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

def error_response(status_code: int, message: str, details: dict = None):
    response = {
        "success": False,
        "error": {
            "code": status_code,
            "message": message
        }
    }
    if details:
        response["error"]["details"] = details
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    error_msg = f"HTTP exception handler caught: {str(exc)}\nStatus code: {exc.status_code}"
    if exc.status_code >= 500:
        logger.error(error_msg)
    elif exc.status_code >= 400:
        logger.warning(error_msg)
    else:
        logger.info(error_msg)
    
    headers = getattr(exc, 'headers', None)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.status_code, str(exc.detail)),
        headers=headers
    )

@app.exception_handler(RequestValidationError)
@app.exception_handler(ResponseValidationError)
async def validation_exception_handler(request: Request, exc: Exception):
    error_msg = f"Validation error: {str(exc)}"
    logger.warning(error_msg)
    return JSONResponse(
        status_code=422,
        content=error_response(
            422,
            "Validation Error",
            {"errors": exc.errors() if hasattr(exc, 'errors') else str(exc)}
        )
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"Global exception handler caught: {str(exc)}\n{traceback.format_exc()}"
    logger.error(error_msg)

    return JSONResponse(
        status_code=500,
        content=error_response(
            500,
            "Internal Server Error",
            {"traceback": traceback.format_exc()}
        )
    )

app.include_router(router)
