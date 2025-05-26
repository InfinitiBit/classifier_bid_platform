import aiohttp
from app.utils.logging import setup_logging
from typing import Dict, Any

logger = setup_logging()


async def notify_backend_status(backend_url: str, analysis_task_id: str, result: Dict[str, Any]) -> object:
    """Notify backend with analysis status update"""
    try:
        # Add authentication
        auth = aiohttp.BasicAuth(login="admin", password="pass123")

        async with aiohttp.ClientSession(auth=auth) as session:
            endpoint = f"{backend_url.rstrip('/')}/analyzers/{analysis_task_id}/subtasks"
            async with session.post(endpoint, json=result) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to update status for analysis task {analysis_task_id}: {await response.text()}")
                else:
                    logger.info(f"Successfully updated status for analysis task {analysis_task_id}")
    except Exception as e:
        logger.error(f"Error updating status for analysis task {analysis_task_id}: {str(e)}")