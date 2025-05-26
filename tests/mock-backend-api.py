from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn
import logging
import json
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mock_api.log")
    ]
)
logger = logging.getLogger("mock-pricing-api")

# Create app
app = FastAPI(title="Raw Response Logger for Mock API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage for received notifications
STORAGE_DIR = "notifications"
os.makedirs(STORAGE_DIR, exist_ok=True)


# Status update model with taskFriendlyName added
class StatusUpdate(BaseModel):
    taskName: str
    taskFriendlyName: Optional[str] = None
    message: Optional[str] = None
    progress: Optional[int] = None


# Work package model
class WorkPackage(BaseModel):
    code: str
    name: str
    estimatedHours: int
    category: Optional[str] = None
    description: Optional[str] = None


# Analysis detail model
class AnalysisDetail(BaseModel):
    area: str
    decision: Optional[str] = None
    description: Optional[str] = None


# Analysis report model
class AnalysisReport(BaseModel):
    attributeName: str
    analysisSummary: str
    reference: Optional[str] = None
    analysisDetails: List[AnalysisDetail] = []


# Pricing response model
class PricingResponse(BaseModel):
    message: Optional[str] = None
    workPackages: List[WorkPackage]
    analysisReport: Optional[List[AnalysisReport]] = []
    fileExtractedReport: Optional[List[AnalysisReport]] = []


def save_notification(task_id: str, notification_type: str, data: Dict[str, Any]):
    """Save notification data to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{STORAGE_DIR}/{task_id}_{notification_type}_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info(f"Saved notification to {filename}")


# Middleware to log raw responses
class ResponseLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Process the request
        response = await call_next(request)

        # Get the path
        path = request.url.path

        # Try to get the body (doesn't work for StreamingResponse)
        if hasattr(response, "body"):
            try:
                # Get the raw response body
                raw_body = response.body

                if raw_body:
                    # Try to decode and parse as JSON if possible
                    try:
                        body_str = raw_body.decode("utf-8")
                        body_json = json.loads(body_str)
                        print(f"\nRaw response from {path}:\n{body_str}\n")
                    except:
                        # Fallback if not JSON or not utf-8
                        print(f"\nRaw response from {path} (non-JSON):\n{raw_body}\n")
            except:
                print(f"\nCould not access response body for {path}\n")

        return response


# Add the middleware
app.add_middleware(ResponseLoggerMiddleware)


@app.get("/")
def read_root():
    return {"message": "Raw Response Logger for Mock API is running"}


# Original endpoints (keeping these for backward compatibility)
@app.post("/analyzers/{task_id}/status")
async def receive_status(task_id: str, status: StatusUpdate):
    """Endpoint for status notifications"""
    friendly_name = status.taskFriendlyName or status.taskName
    logger.info(f"Received status update for task {task_id}: {status.taskName} (Friendly: {friendly_name})")

    # Save notification
    save_notification(task_id, "status", status.dict())

    return {
        "status": "received",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyzers/{task_id}/completion")
async def receive_completion(task_id: str, data: Dict[str, Any]):
    """Endpoint for general completion notifications"""
    logger.info(f"Received completion notification for task {task_id}")

    # Save notification
    save_notification(task_id, "completion", data)

    return {
        "status": "received",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyzers/{task_id}/pricing-completion")
async def receive_pricing_completion(task_id: str, response: PricingResponse):
    """Endpoint for pricing completion notifications"""
    logger.info(f"Received pricing completion for task {task_id} with {len(response.workPackages)} work packages")

    # Save notification
    save_notification(task_id, "pricing_completion", response.dict())

    return {
        "status": "received",
        "task_id": task_id,
        "workPackagesCount": len(response.workPackages),
        "timestamp": datetime.now().isoformat()
    }


# NEW ENDPOINTS based on actual application requests
@app.post("/analyzers/{task_id}/subtasks")
async def receive_subtasks(task_id: str, data: Dict[str, Any]):
    """Endpoint for subtask status updates"""
    logger.info(f"Received subtask update for task {task_id}")

    # Extract task name and friendly name if available
    task_name = data.get("taskName", "unknown")
    task_friendly_name = data.get("taskFriendlyName", task_name)

    # Log both task name and friendly name
    logger.info(f"Task: {task_name} | Friendly Name: {task_friendly_name}")

    # Save notification
    save_notification(task_id, "subtasks", data)

    return {
        "status": "received",
        "task_id": task_id,
        "taskName": task_name,
        "taskFriendlyName": task_friendly_name,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyzers/{task_id}/update-pricing")
async def receive_pricing_update(task_id: str, data: Dict[str, Any]):
    """Endpoint for pricing updates"""
    logger.info(f"Received pricing update for task {task_id}")

    # Count work packages if available
    work_packages_count = len(data.get("workPackages", []))
    logger.info(f"Work packages count: {work_packages_count}")

    # Save notification
    save_notification(task_id, "pricing_update", data)

    return {
        "status": "received",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyzers/{task_id}/update-report")
async def receive_report_update(task_id: str, data: Dict[str, Any]):
    """Endpoint for report updates"""
    logger.info(f"Received report update for task {task_id}")

    # Save notification
    save_notification(task_id, "report_update", data)

    return {
        "status": "received",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyzers/{task_id}/update-technical")
async def receive_technical_update(task_id: str, data: Dict[str, Any]):
    """Endpoint for technical updates"""
    logger.info(f"Received technical update for task {task_id}")

    # Save notification
    save_notification(task_id, "technical_update", data)

    return {
        "status": "received",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/notifications/{task_id}")
async def get_notifications(task_id: str):
    """Retrieve all notifications for a task"""
    files = [f for f in os.listdir(STORAGE_DIR) if f.startswith(f"{task_id}_")]

    if not files:
        raise HTTPException(status_code=404, detail=f"No notifications found for task {task_id}")

    notifications = []
    for file in files:
        with open(f"{STORAGE_DIR}/{file}", "r") as f:
            notification = json.load(f)
            notifications.append({
                "type": file.split("_")[1],
                "timestamp": file.split("_")[2].replace(".json", ""),
                "data": notification
            })

    return {"task_id": task_id, "notifications": notifications}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Raw Response Logger for Mock API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8010, help="Port to bind to")
    args = parser.parse_args()

    logger.info(f"Starting mock API server on {args.host}:{args.port}")
    logger.info("Raw response logging is enabled - check console for exact response data")
    uvicorn.run(app, host=args.host, port=args.port)