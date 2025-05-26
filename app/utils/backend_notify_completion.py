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

        async with aiohttp.ClientSession(auth=auth) as session:
            endpoint = f"{backend_url.rstrip('/')}/analyzers/{analysis_task_id}/update-report"
            async with session.post(endpoint, json=result) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to update report for analysis task {analysis_task_id}: {await response.text()}")
                else:
                    logger.info(f"Successfully updated report for analysis task {analysis_task_id}")
    except Exception as e:
        logger.error(f"Error updating report for analysis task {analysis_task_id}: {str(e)}")


async def notify_backend_completion_pricing(backend_url: str, analysis_task_id: str, result: Dict[str, Any]):
    """Notify backend with analysis report update"""
    try:
        # Using specific credentials for auth
        auth = aiohttp.BasicAuth(login="admin", password="pass123")

        async with aiohttp.ClientSession(auth=auth) as session:
            endpoint = f"{backend_url.rstrip('/')}/analyzers/{analysis_task_id}/update-pricing"
            async with session.post(endpoint, json=result) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to update report for analysis task {analysis_task_id}: {await response.text()}")
                else:
                    logger.info(f"Successfully updated report for analysis task {analysis_task_id}")
    except Exception as e:
        logger.error(f"Error updating report for analysis task {analysis_task_id}: {str(e)}")



async def notify_backend_completion_with_file(
        backend_url: str,
        analysis_task_id: str,
        result: Dict[str, Any],
        docx_file_path: Optional[str] = None
):
    """
    Notify backend with technical offer file upload

    Args:
        backend_url: Base URL of the backend API
        analysis_task_id: ID of the analysis task
        result: Analysis result data (not used in this endpoint)
        docx_file_path: Path to the generated DOCX file (optional)
    """
    try:
        # Using specific credentials for auth
        auth = aiohttp.BasicAuth(login="admin", password="pass123")

        async with aiohttp.ClientSession(auth=auth) as session:
            # Use the correct endpoint URL
            endpoint = f"{backend_url.rstrip('/')}/analyzers/{analysis_task_id}/update-technical"

            # Create form data for multipart request
            form_data = FormData()

            # Add the DOCX file if available with the expected field name "technicalOffer"
            if docx_file_path and Path(docx_file_path).exists():
                docx_path = Path(docx_file_path)
                form_data.add_field('technicalOffer',
                                    open(docx_path, 'rb'),
                                    filename=docx_path.name,
                                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                logger.info(f"Added technical offer file {docx_path} to request")
            else:
                # Add an empty file if no file is available
                form_data.add_field('technicalOffer', b'',
                                    filename='empty.docx',
                                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                logger.info("No file available - sending empty technical offer")

            # Send the request with multipart form data
            async with session.post(endpoint, data=form_data) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to upload technical offer for task {analysis_task_id}: {await response.text()}")
                else:
                    logger.info(f"Successfully uploaded technical offer for task {analysis_task_id}")
    except Exception as e:
        logger.error(f"Error uploading technical offer for task {analysis_task_id}: {str(e)}")


async def notify_backend_completion_with_file_commercial(
        backend_url: str,
        analysis_task_id: str,
        result: Dict[str, Any],
        docx_file_path: Optional[str] = None
):
    """
    Notify backend with commercial offer file upload

    Args:
        backend_url: Base URL of the backend API
        analysis_task_id: ID of the analysis task
        result: Analysis result data (not used in this endpoint)
        docx_file_path: Path to the generated DOCX file (optional)
    """
    try:
        # Using specific credentials for auth
        auth = aiohttp.BasicAuth(login="admin", password="pass123")

        async with aiohttp.ClientSession(auth=auth) as session:
            # Use the correct endpoint URL
            endpoint = f"{backend_url.rstrip('/')}/analyzers/{analysis_task_id}/update-commercial"

            # Create form data for multipart request
            form_data = FormData()

            # Add the DOCX file if available with the expected field name "commercialOffer"
            if docx_file_path and Path(docx_file_path).exists():
                docx_path = Path(docx_file_path)
                form_data.add_field('commercialOffer',
                                    open(docx_path, 'rb'),
                                    filename=docx_path.name,
                                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                logger.info(f"Added commercial offer file {docx_path} to request")
            else:
                # Add an empty file if no file is available
                form_data.add_field('commercialOffer', b'',
                                    filename='empty.docx',
                                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                logger.info("No file available - sending empty commercial offer")

            # Send the request with multipart form data
            async with session.post(endpoint, data=form_data) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to upload commercial offer for task {analysis_task_id}: {await response.text()}")
                else:
                    logger.info(f"Successfully uploaded commercial offer for task {analysis_task_id}")
    except Exception as e:
        logger.error(f"Error uploading commercial offer for task {analysis_task_id}: {str(e)}")