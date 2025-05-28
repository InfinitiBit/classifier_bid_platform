import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import secrets
from app.routes.healthcheck import router as healthcheck
from app.routes.classification_routes import router as classification_router
from app.utils.logging import setup_logging
from app.utils.thread_manager import thread_manager
from app.utils.storage import LocalStorageManager
from app.utils.scheduler import cleanup_scheduler

logger = setup_logging()

# Add security setup
security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify HTTP Basic Auth credentials"""
    is_correct_username = secrets.compare_digest(credentials.username, "admin")
    is_correct_password = secrets.compare_digest(credentials.password, "password123")

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


app = FastAPI(
    title="Document Classification API",
    description="Enhanced Document Classification System with AI Agents",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(healthcheck, tags=["health"])
app.include_router(classification_router, prefix="/classification", tags=["document-classification"], dependencies=[Depends(verify_credentials)])




# @app.on_event("startup")
# async def startup_event():
#     cleanup_scheduler.schedule_cleanup(minutes=120)
#     cleanup_scheduler.start()
#     logger.info("Application started with cleanup scheduler")
#
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     cleanup_scheduler.stop()
#     logger.info("Application shutdown, cleanup scheduler stopped")


# Add task monitoring endpoints with authentication
@app.get("/tasks/status")
async def get_all_tasks_status(username: str = Depends(verify_credentials)):
    """Get status of all agent_tasks"""
    thread_manager.cleanup()  # Cleanup old agent_tasks
    return {
        "active_tasks": len(thread_manager.active_tasks),
        "agent_tasks": thread_manager.active_tasks
    }


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str, username: str = Depends(verify_credentials)):
    """Get status of specific task"""
    # First check thread manager
    thread_status = thread_manager.get_task_status(task_id)
    if thread_status:
        return thread_status

    # If not in thread manager, check storage
    stored_response = await LocalStorageManager.get_response(task_id)
    if stored_response:
        return stored_response

    return {"status": "not_found"}


@app.get("/tasks")
async def list_all_tasks(username: str = Depends(verify_credentials)):
    """Get a list of all agent_tasks with their status"""
    tasks = thread_manager.get_task_status_all()
    return {
        "total_tasks": len(tasks),
        "active_tasks": sum(1 for task in tasks.values() if task['status'] == 'processing'),
        "completed_tasks": sum(1 for task in tasks.values() if task['status'] == 'completed'),
        "failed_tasks": sum(1 for task in tasks.values() if task['status'] == 'failed'),
        "agent_tasks": tasks
    }


# Add maintenance endpoints with authentication
@app.post("/maintenance/cleanup/responses")
async def trigger_responses_cleanup(username: str = Depends(verify_credentials)):
    """Manually trigger responses cleanup"""
    try:
        result = await LocalStorageManager.cleanup_responses()
        return {
            "status": "success",
            "details": result
        }
    except Exception as e:
        logger.error(f"Error during manual responses cleanup: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/maintenance/cleanup/extracted")
async def trigger_extracted_cleanup(username: str = Depends(verify_credentials)):
    """Manually trigger extracted folder cleanup"""
    try:
        result = await LocalStorageManager.cleanup_extracted()
        return {
            "status": "success",
            "details": result
        }
    except Exception as e:
        logger.error(f"Error during manual extracted cleanup: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)