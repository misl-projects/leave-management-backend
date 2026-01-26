from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from leave_management_workflow import process_incoming_emails

app = FastAPI(title="MISL Leave Email Processor")

# Scheduler runs in background
scheduler = BackgroundScheduler()
scheduler.add_job(process_incoming_emails, 'interval', seconds=15)  # check every 15 sec
scheduler.start()

@app.get("/")
def read_root():
    return {"status": "MISL Leave Processor Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
