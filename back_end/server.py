from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from utils.tools import create_error_response, create_success_response
import os
from pathlib import Path
from main import run_analysis, run_chat, run_report
import uuid
import logging
from back_end.services.chat_service import ChatService, ConfirmationStatus, WorkflowContext

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
        logger.info('the html file is stored at:', file_path)

        # 将上传的文件内容保存到磁盘
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 运行分析流程
        shared = run_analysis(str(file_path.absolute()))
        
        session_chat_flow = WorkflowContext()
        chat_service = ChatService(session_chat_flow)
        updated_shared = chat_service.initialize_chat(shared)
        status = chat_service.chat_flow.current_state.value
        initial_message = chat_service.get_instructions(shared,status)

        logger.info('now we initialized status as:', status)

        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "shared": shared,
            "state": status if not updated_shared.get("all_confirmed") else "completed",
            'chat_service': chat_service,
            'chat_flow': session_chat_flow
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

@app.post('/analyze-contract/{session_id}')
async def analyze_contract(session_id: str, file: UploadFile = File(...)):
    
    # 检查session是否存在
    session = sessions.get(session_id)
    if not session:
        return create_error_response(
            "SESSION_NOT_FOUND",
            f"Session {session_id} not found",
            404
        )
    
    # 检查shared数据
    if 'shared' not in session:
        return create_error_response(
            "SHARED_DATA_NOT_FOUND",
            f"Shared data not found in session {session_id}"
        )
    
    # 检查riskBot
    if 'riskBot' not in session['shared']:
        return create_error_response(
            "RISK_BOT_NOT_FOUND",
            f"RiskBot not found in session {session_id}"
        )
    
    curr_shared = session['shared']
    risk_bot = curr_shared['riskBot']
    chat_flow = session['chat_flow']
    
    # 处理文件
    try:
        os.makedirs("uploads", exist_ok=True)
        
        # 创建文件路径
        file_path = os.path.join("uploads", file.filename)
        
        # 将上传的文件内容保存到磁盘
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f'The file is stored at: {file_path}')
        
        analysis_result = risk_bot.contract_check(file_path)
        
        logger.info(f"Contract analysis completed successfully for session {session_id}")

        sessions[session_id]['contract_analysis'] = analysis_result

        content = {
            'shared': curr_shared,
            'status': 'next',
        }

        chat_flow.process(content)

        sessions[session_id]['chat_flow'] = chat_flow

        return create_success_response(
            data={"file_path": str(file_path)},
            message="Contract analysis completed successfully"
        )
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        # You can either use create_error_response or directly return JSONResponse
        return JSONResponse(
            content={
                'error': 'CHAT_ERROR',
                'message': f"Error during contract analysis: {str(e)}"
            },
            status_code=500
        )

@app.post("/chat/{session_id}")
async def chat(session_id: str, chat_message: ChatMessage):
    session = sessions.get(session_id)
    if not session:
        return create_error_response(
            "SESSION_NOT_FOUND",
            f"Session {session_id} not found",
            404
        )
    chat_service = session['chat_service']
    chat_flow = session['chat_flow']

    status = chat_flow.current_state
    logger.info('when processing input, we are in the status of:', status)

    if status == "completed":
        return {
            "status": "completed",
            "message": "该会话已完成所有组件确认，请上传新html文件"
        }
    
    try:
        # 处理用户输入
        status, updated_shared, reply = chat_service.process_user_input(
            session["shared"],
            chat_message.message,
            status
        )

        # 更新会话状态
        session["shared"] = updated_shared
        
        if status == True:
            session["state"] = "completed"
            
            return {
                "status": "completed",
                "message": reply,
            }
        
        return {
            "status": status,
            "message": reply,
            "current_component_idx": updated_shared.get("current_component_idx")
        }
        
    except Exception as e:
        logger.error(f"Error during chat: {str(e)}", exc_info=True)
        return create_error_response(
            'CHAT_ERROR',
            f"Error during contract analysis: {str(e)}",
            500
        )

# 获取当前会话状态
@app.get("/sessions/{session_id}")
async def get_session_status(session_id: str):
    session = sessions.get(session_id)
    if not session:
        return create_error_response(
            "SESSION_NOT_FOUND",
            f"Session {session_id} not found",
            404
        )
    
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