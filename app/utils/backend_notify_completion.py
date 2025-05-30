import aiohttp
from aiohttp import FormData
from pathlib import Path
from app.utils.logging import setup_logging
from typing import Dict, Any, Optional

logger = setup_logging()


async def notify_backend_completion(backend_url: str, analysis_task_id: str, result: Dict[str, Any]):
    """Notify backend with analysis report update"""
    try:
        # Using specific credentials for auth
        auth = aiohttp.BasicAuth(login="admin", password="pass123")

        result.update({"message": "classification completion"})

        async with aiohttp.ClientSession(auth=auth) as session:
            endpoint = f"{backend_url.rstrip('/')}/classifiers/{analysis_task_id}/update-report"
            async with session.post(endpoint, json=result) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to update report for analysis task {analysis_task_id}: {await response.text()}, response.status: {response.status})")
                else:
                    logger.info(f"Successfully updated report for analysis task {analysis_task_id}")
    except Exception as e:
        logger.error(f"Error updating report for analysis task {analysis_task_id}: {str(e)}")


