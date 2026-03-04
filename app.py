from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from leave_management_workflow import process_incoming_emails, process_status_change_notifications

app = FastAPI(title="MISL Leave Email Processor")

# Scheduler runs in background
scheduler = BackgroundScheduler(
    executors={"default": ThreadPoolExecutor(2)},
    job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
)
scheduler.add_job(process_incoming_emails, 'interval', seconds=15)  # check every 15 sec
scheduler.add_job(process_status_change_notifications, 'interval', seconds=15)  # check status override queue
scheduler.start()

@app.get("/")
def read_root():
    return {"status": "MISL Leave Processor Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
