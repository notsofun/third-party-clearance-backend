from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from utils.tools import create_error_response, create_success_response
import os
from back_end.config import settings
from pathlib import Path
from log_config import configure_logging, get_logger
from contextlib import asynccontextmanager
from back_end.services.clearance_facade import ClearanceError, clearance_facade

try:
    from back_end.mcp_server import clearance_mcp
except ModuleNotFoundError as exc:
    if exc.name != "mcp":
        raise
    clearance_mcp = None

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
    # 初始化API基础URL
    settings.init_api_base_url()
    logger.info(f"API base URL: {settings.API_BASE_URL}")
    if clearance_mcp is not None:
        async with clearance_mcp.session_manager.run():
            yield
    else:
        logger.warning("MCP SDK is not installed; /mcp endpoint is disabled.")
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

class ChatMessage(BaseModel):
    message: str

# 确保上传目录存在
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

if clearance_mcp is not None:
    app.mount("/mcp", clearance_mcp.streamable_http_app())

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        result = clearance_facade.start_analysis_from_bytes(
            content,
            file.filename,
            source="rest",
        )
        logger.info("Initialized clearance session %s", result["session_id"])
        return result
    except ClearanceError as e:
        return create_error_response(
            "INVALID_UPLOAD",
            error_message=str(e),
            status_code=400,
        )
    except Exception as e:
        return create_error_response(
            "Error during analysis",
            error_message=str(e),
            status_code=500
        )

@app.post('/analyze-contract/{session_id}')
async def analyze_contract(session_id: str, file: UploadFile = File(...)):
    try:
        content = await file.read()
        file_path = clearance_facade.save_upload_bytes(content, file.filename)
        logger.info("The contract file is stored at: %s", file_path)
        result = clearance_facade.analyze_contract(session_id, file_path)
        logger.info(f"Contract analysis completed successfully for session {session_id}")
        return create_success_response(
            data={"file_path": str(file_path)},
            message=result["message"]
        )
    except ClearanceError as e:
        return create_error_response(
            "CONTRACT_ANALYSIS_ERROR",
            str(e),
            400,
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
    try:
        return clearance_facade.chat(session_id, chat_message.message)
    except ClearanceError as e:
        return create_error_response(
            "SESSION_NOT_FOUND",
            str(e),
            404,
        )
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
    try:
        summary = clearance_facade.get_session(session_id)
    except ClearanceError:
        return create_error_response(
            "SESSION_NOT_FOUND",
            f"Session {session_id} not found",
            404
        )

    return {
        "status": summary["status"],
        "components": summary["components"],
        "current_component_idx": summary["current_component_idx"],
        "progress": summary["progress"],
        "download": summary["download"],
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
    
    # 初始化API基础URL
    settings.HOST = "127.0.0.1"
    settings.PORT = 8000
    settings.init_api_base_url()
    
    # 启动服务器
    uvicorn.run(
        "back_end.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_config=None
    )
