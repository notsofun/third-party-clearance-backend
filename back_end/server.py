from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn
from utils.tools import create_error_response, create_success_response
import os,re
from pathlib import Path
from main import run_analysis, run_report
import uuid
from log_config import configure_logging, get_logger
from back_end.services.chat_service import ChatService, WorkflowContext
from contextlib import asynccontextmanager
from back_end.items_utils.item_types import ConfirmationStatus

configure_logging()
logger = get_logger(__name__)

def startup_event():
    """应用启动时执行，确保日志系统已初始化"""
    logger.info("FastAPI应用启动")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时再次确保日志配置正确
    # 这对热重载很重要
    logger.info("FastAPI应用启动")
    yield
    logger.info("FastAPI应用关闭")
    # 确保日志刷新
    for handler in logger.root.handlers:
        handler.flush()

app = FastAPI(lifespan=lifespan)

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
        logger.info('the html file is stored at: %s', file_path)

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
        initial_message = chat_service.get_instructions(status)

        logger.info('now we initialized status as: %s', status)

        session_id = str(uuid.uuid4())

        sessions[session_id] = {
            "shared": shared,
            "state": status if not updated_shared.get("all_confirmed") else "completed",
            'chat_service': chat_service,
            'chat_flow': chat_service.chat_flow
        }
        
        return {
            "session_id": session_id,
            "components": updated_shared.get("toBeConfirmedComps", []),
            "message": initial_message,
            "status": sessions[session_id]["state"]
        }
        
    except Exception as e:
        return create_error_response(
            "Error during analysis",
            error_message=str(e),
            status_code=500
        )

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
    chat_service = session['chat_service']
    
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
        # 这里会生成结果为next的回答
        logger.info(f"Contract analysis completed successfully for session {session_id}")
        sessions[session_id]['contract_analysis'] = analysis_result

        status = chat_flow.current_state

        content = {
            'shared': curr_shared,
            'status': 'next',
        }

        # Status here should be transitted to toDependency
        updated_status = chat_flow.process(content).value

        # Since the status has changed, here should return an instruction for dependency checking
        updated_status, updated_shared, message = chat_service._status_check(
            curr_shared,
            updated_status,
            status,
            'next',
            None
        )

        sessions[session_id].update({
            'chat_flow': chat_flow,
            'state': updated_status,
            'shared': updated_shared,
            'chat_service' : chat_service
        })

        return create_success_response(
            data={"file_path": str(file_path)},
            message= message
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

    status = chat_flow.current_state.value
    logger.info('server: before processing input, we are in the status of: %s', status)

    # 用于对话结束后减少无用请求
    if status == ConfirmationStatus.COMPLETED.value:
        session["state"] = ConfirmationStatus.COMPLETED.value
        logger.info("We have finished all checking in current session, please reupload a new license info file to start a new session. ")
        return {
            "status": "completed",
            "message": "We have finished all checking in current session, please reupload a new license info file to start a new session."
        }
    
    try:
        # 处理用户输入
        status, updated_shared, reply = chat_service.process_user_input(
            session["shared"],
            chat_message.message,
            status
        )

        download_info = None

        if status == ConfirmationStatus.OSSGENERATION.value and session.get('ReportNotGenerated', True) == True:
            logger.info('All checking finished. Now we are generating the report...')
            updated_shared['session_id'] = session_id
            run_report(updated_shared)
            sessions[session_id]['ReportGenerated'] = False
            # 添加文件下载URL到响应
            file_name, download_url = 'Final_OSS_Readme.docx', f"download/{session_id}"
            # 设置下载信息
            download_info = {
                "available": True,
                "url": download_url,
                "filename": file_name
            }

        sessions[session_id].update({
        'chat_flow': chat_flow,
        'state': status,
        'shared': updated_shared,
        'chat_service' : chat_service,
        })

        # 构建基本响应
        response = {
            "status": status,
            "message": reply,
            "current_component_idx": updated_shared.get("current_component_idx")
        }
        
        # 如果有下载信息，添加到响应中
        if download_info:
            response["download"] = download_info

        return response

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

#http://127.0.0.1:8000/download/c58af74b-08fc-49f5-842a-400d4935d469
@app.get("/download/{session_id}")
async def download_oss(session_id: str, file_name: str = "Final_OSS_Readme.docx"):
    
    file_path = f"downloads/{session_id}/Final_OSS_Readme.docx"
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return create_error_response(
            "FILE NOT FOUND",
            'Sorry, we have not found the file you wanted',
            404
        )
    
    # 返回文件作为响应
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

# 在项目根路径下通过uvicorn back_end.server:app --reload --host 127.0.0.1 --port 8000激活服务器
if __name__ == "__main__":
    import uvicorn
    import os
    import sys
    
    # 将当前目录加入到Python路径
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uvicorn.run("back_end.server:app", host="127.0.0.1", port=8000, reload=True, log_config=None)