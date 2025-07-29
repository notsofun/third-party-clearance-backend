from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from pathlib import Path
from main import run_analysis, run_chat, run_report
import uuid
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("msal").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)



app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}
# 确保上传目录存在
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    try:
        # 保存上传的文件
        file_path = UPLOAD_DIR / file.filename
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # 运行分析流程
        shared = run_analysis(str(file_path.absolute()))
        
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "shared": shared,
            "state": "ready_for_chat"
        }
        
        return {
            "session_id": session_id,
            "components": shared.get("toBeConfirmedComps", [])
        }
        
    except Exception as e:
        logger.error(f"Error during file analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/{session_id}")
async def chat(session_id: str, message: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        is_complete, shared = run_chat(session["shared"])
        session["shared"] = shared
        
        if is_complete:
            result = run_report(shared)
            session["state"] = "completed"
            return {
                "status": "completed",
                "report": result
            }
        
        return {
            "status": "continue",
            "reply": shared.get("last_reply")
        }
        
    except Exception as e:
        logger.error(f"Error during chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)