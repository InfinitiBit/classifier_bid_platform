from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.utils.logging import setup_logging
from app.utils.storage import LocalStorageManager

logger = setup_logging()
class CleanupScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    async def cleanup_task(self):
        """Scheduled task to clean up extracted folder only"""
        try:
            logger.info("Starting scheduled extracted folder cleanup")
            result = await LocalStorageManager.cleanup_extracted()
            logger.info(f"Scheduled cleanup completed: {result}")
            return result
        except Exception as e:
            logger.error(f"Error during scheduled cleanup: {str(e)}")
            return {"error": str(e)}

    def schedule_cleanup(self, minutes: int = 30):
        """Schedule the extracted folder cleanup task"""
        self.scheduler.add_job(
            self.cleanup_task,
            IntervalTrigger(minutes=minutes),
            id='extracted_cleanup_task',
            name='Extracted Folder Cleanup',
            replace_existing=True
        )
        logger.info(f"Scheduled extracted folder cleanup task to run every {minutes} minute(s)")

    def start(self):
        self.scheduler.start()
        logger.info("Cleanup scheduler started")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Cleanup scheduler stopped")

cleanup_scheduler = CleanupScheduler()