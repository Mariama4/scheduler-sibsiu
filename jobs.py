from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from helpers import helper


def set_scheduled_jobs(scheduler, bot):
    scheduler.add_job(helper.update_schedule_and_notify_users,
                      "interval",
                      hours=6,
                      args=(bot,),
                      next_run_time=datetime.now()
                      )


def init_jobs(bot):
    scheduler = AsyncIOScheduler()
    set_scheduled_jobs(scheduler, bot)
    scheduler.start()
