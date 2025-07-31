from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from pathlib import Path
from main import run_analysis, run_chat, run_report
import uuid
import logging
from back_end.services.chat_service import ChatService

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

chat_service = ChatService()

class ChatMessage(BaseModel):
    message: str

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
        
        updated_shared, initial_message = chat_service.initialize_chat(shared)

        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "shared": shared,
            "state": "in_progress" if not updated_shared.get("all_confirmed") else "completed"
        }
        
        return {
            "session_id": session_id,
            "components": updated_shared.get("toBeConfirmedComps", []),
            "message": initial_message,
            "status": sessions[session_id]["state"]
        }
        
    except Exception as e:
        logger.error(f"Error during file analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/{session_id}")
async def chat(session_id: str, chat_message: ChatMessage):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session["state"] == "completed":
        return {
            "status": "completed",
            "message": "该会话已完成所有组件确认，请上传新html文件"
        }
    
    try:
        # 处理用户输入
        is_complete, updated_shared, reply = chat_service.process_user_input(
            session["shared"],
            chat_message.message
        )
        
        # 更新会话状态
        session["shared"] = updated_shared
        
        if is_complete:
            session["state"] = "completed"
            
            # 生成确认结果摘要
            comps = updated_shared.get("toBeConfirmedComps", [])
            summary = {
                "total": len(comps),
                "passed": len([c for c in comps if c.get("status") == "passed"]),
                "discarded": len([c for c in comps if c.get("status") == "discarded"])
            }
            
            return {
                "status": "completed",
                "message": reply,
                "components": comps,
                "summary": summary
            }
        
        return {
            "status": "continue",
            "message": reply,
            "current_component_idx": updated_shared.get("current_component_idx")
        }
        
    except Exception as e:
        logger.error(f"Error during chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# 获取当前会话状态
@app.get("/sessions/{session_id}")
async def get_session_status(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    shared = session["shared"]
    current_idx = shared.get("current_component_idx")
    comps = shared.get("toBeConfirmedComps", [])
    
    return {
        "status": session["state"],
        "components": comps,
        "current_component_idx": current_idx if current_idx is not None else -1
    }


# 在项目根路径下通过uvicorn back_end.server:app --reload --host 127.0.0.1 --port 8000激活服务器
if __name__ == "__main__":
    import uvicorn
    import importlib
    import os
    import sys
    
    # 将当前目录加入到Python路径
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uvicorn.run("back_end.server:app", host="127.0.0.1", port=8000, reload=True)