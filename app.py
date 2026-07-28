import os
import io
import logging
from typing import List, Dict, Any, Optional
from google import genai
from pydantic import BaseModel, Field
import uvicorn
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pdf-insight-hub")

app = FastAPI(title="SaaS PDF Insight Hub Server")

documents_store: Dict[str, Dict[str, Any]] = {}

CACHE_DIR = "document_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def save_to_cache(filename: str, text: str, pages: int, words: int, size: int):
    try:
        meta_path = os.path.join(CACHE_DIR, f"{filename}.meta")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(f"{pages},{words},{size}")
        text_path = os.path.join(CACHE_DIR, f"{filename}.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Saved {filename} to local cache.")
    except Exception as e:
        logger.error(f"Failed to cache document {filename}: {str(e)}")

def load_cache():
    try:
        if not os.path.exists(CACHE_DIR):
            return
        for file in os.listdir(CACHE_DIR):
            if file.endswith(".txt"):
                filename = file[:-4]
                meta_path = os.path.join(CACHE_DIR, f"{filename}.meta")
                text_path = os.path.join(CACHE_DIR, file)
                
                if os.path.exists(meta_path) and os.path.exists(text_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_data = f.read().split(",")
                        if len(meta_data) == 3:
                            pages, words, size = map(int, meta_data)
                        else:
                            pages, words, size = int(meta_data[0]), int(meta_data[1]), 0
                    with open(text_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    documents_store[filename] = {
                        "text": text,
                        "pages": pages,
                        "words": words,
                        "size": size
                    }
        logger.info(f"Loaded {len(documents_store)} documents from local cache.")
    except Exception as e:
        logger.error(f"Failed to load document cache: {str(e)}")

def clear_cache():
    try:
        if os.path.exists(CACHE_DIR):
            import shutil
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
            logger.info("Purged local cache directory.")
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")

load_cache()

class DashboardStats(BaseModel):
    pageCount: int = Field(description="Total pages of all uploaded documents combined")
    wordCount: int = Field(description="Total word count of all uploaded documents combined")
    riskCount: int = Field(description="Number of critical issues, warnings, risks, or technical debt points found in the documents")
    sentiment: str = Field(description="Overall sentiment of the documents (e.g. 'Positive', 'Neutral', 'Constructive', 'Negative')")

class TopicData(BaseModel):
    labels: List[str] = Field(description="Top 5-6 core topics or features discussed in the documents")
    values: List[float] = Field(description="Relevance percentage score (0 to 100) for each topic")

class SentimentBreakdown(BaseModel):
    labels: List[str] = Field(description="Labels showing 'Positive', 'Neutral', 'Negative' sentiment segments")
    values: List[float] = Field(description="Percentage distribution of sentiment segments (must sum up to 100)")

class Takeaway(BaseModel):
    type: str = Field(description="Highlight type: must be 'success' (for positive/next steps), 'warning' (for risks/actions required), or 'primary' (for general info)")
    icon: str = Field(description="Lucide icon name suitable for the takeaway. Example: 'check-circle', 'alert-triangle', 'help-circle', 'shield', 'zap', 'activity', 'file-text'")
    text: str = Field(description="Concise description of a major finding, deadline, software milestone, or next step")

class AnalysisResult(BaseModel):
    summary: str = Field(description="Comprehensive executive summary in Markdown format. Organize with clear heading structures, bullet points, and highlight software solutions, technical details, or business impact.")
    stats: DashboardStats
    topics: TopicData
    sentimentBreakdown: SentimentBreakdown
    takeaways: List[Takeaway]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatPayload(BaseModel):
    message: str
    history: List[ChatMessage]

def get_gemini_client(api_key_header: Optional[str] = None):
    """
    Initializes the Gemini Client. Checks the request header first,
    then checks local environment variables.
    """
    api_key = api_key_header or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key is missing. Please configure it in the web dashboard or set the GEMINI_API_KEY environment variable."
        )
    
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        logger.error("Failed to import google-genai. Make sure it is installed.")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: google-genai package is not installed."
        )


@app.get("/api/files")
async def get_files():
    """Returns the list of loaded files from memory/cache."""
    files_list = []
    for filename, doc in documents_store.items():
        files_list.append({
            "name": filename,
            "page_count": doc["pages"],
            "word_count": doc["words"],
            "size": doc["size"]
        })
    return files_list

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Receives a PDF, parses its text contents using pypdf,
    and updates the in-memory document store.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are allowed.")
    
    try:
        contents = await file.read()
        pdf_file = io.BytesIO(contents)
        reader = PdfReader(pdf_file)
        
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        page_count = len(reader.pages)
        word_count = len(text.split())
        
        documents_store[file.filename] = {
            "text": text,
            "pages": page_count,
            "words": word_count,
            "size": len(contents)
        }
        
        save_to_cache(file.filename, text, page_count, word_count, len(contents))
        
        logger.info(f"Successfully processed PDF: {file.filename} ({page_count} pages, {word_count} words)")
        
        return {
            "status": "success",
            "filename": file.filename,
            "page_count": page_count,
            "word_count": word_count
        }
    except Exception as e:
        logger.error(f"Error processing PDF {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

@app.post("/api/delete")
async def delete_document(payload: Dict[str, str]):
    """Deletes a specific document from memory and disk cache."""
    filename = payload.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
        
    if filename in documents_store:
        del documents_store[filename]
        try:
            meta_path = os.path.join(CACHE_DIR, f"{filename}.meta")
            text_path = os.path.join(CACHE_DIR, f"{filename}.txt")
            if os.path.exists(meta_path): os.remove(meta_path)
            if os.path.exists(text_path): os.remove(text_path)
            logger.info(f"Deleted {filename} from cache.")
        except Exception as e:
            logger.error(f"Failed to delete cache file for {filename}: {str(e)}")
        return {"status": "success", "filename": filename}
    else:
        raise HTTPException(status_code=404, detail="File not found in store")

@app.post("/api/clear")
async def clear_documents():
    """Clears all parsed PDFs from memory and disk cache."""
    documents_store.clear()
    clear_cache()
    logger.info("Cleared document store and disk cache")
    return {"status": "cleared"}

@app.post("/api/summary", response_model=AnalysisResult)
async def generate_summary(
    x_gemini_api_key: Optional[str] = Header(None),
):
    """
    Merges all uploaded document contents, sends them to Gemini,
    and requests a structured analysis (markdown summary + dashboard metrics).
    """
    if not documents_store:
        raise HTTPException(status_code=400, detail="No documents uploaded. Please upload some files first.")
    
    client = get_gemini_client(x_gemini_api_key)
    
    full_text_list = []
    total_pages = 0
    total_words = 0
    
    for filename, doc in documents_store.items():
        total_pages += doc["pages"]
        total_words += doc["words"]
        full_text_list.append(f"--- START FILE: {filename} ---\n{doc['text']}\n--- END FILE: {filename} ---")
        
    documents_context = "\n\n".join(full_text_list)
    
    prompt = f"""
    You are DIRS AI, an elite Software Solutions Architect and Business Analyst. 
    Analyze the following files related to software solutions and generate:
    1. A detailed, premium Executive Summary in Markdown (under 'summary' key). It should cover:
       - Context and Core Objective of the software/project.
       - Key Technical Design / Architecture highlights.
       - Business Impact or Core Deliverables.
    2. Structured dashboard data matching the requested schema, reflecting key details found in the files.
    
    Guidelines:
    - Base all metrics on actual facts present in the text context.
    - Set the 'pageCount' stats property to exactly {total_pages}.
    - Set the 'wordCount' stats property to exactly {total_words}.
    - Extract topics (under 'topics' key) showing relevance levels (0-100%).
    - Calculate sentiment breakdown (must add up to 100%).
    - Flag critical risks (under 'riskCount' and in 'takeaways' as warnings) like security flaws, missing specs, or aggressive deadlines.
    - Identify major action items or takeaways.
    
    Here is the documents text context:
    {documents_context}
    """
    
    try:
        from google.genai import types
        
        logger.info("Requesting structured analysis from Gemini model...")
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalysisResult,
                temperature=0.2
            )
        )
        
        import json
        result_json = json.loads(response.text)
        logger.info("Successfully received and parsed structured summary from Gemini.")
        return result_json
        
    except Exception as e:
        logger.error(f"Gemini API summary call failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Gemini API Error: {str(e)}"
        )

@app.post("/api/chat")
async def chat_companion(
    payload: ChatPayload,
    x_gemini_api_key: Optional[str] = Header(None)
):
    """
    Answers a question about the uploaded document context,
    taking previous conversation history into account.
    """
    if not documents_store:
        raise HTTPException(status_code=400, detail="No documents available. Please upload files first.")
        
    client = get_gemini_client(x_gemini_api_key)
    
    full_text_list = []
    for filename, doc in documents_store.items():
        full_text_list.append(f"File: {filename}\nContent:\n{doc['text']}")
    documents_context = "\n\n=== DOCUMENT DATABASE ===\n\n" + "\n\n".join(full_text_list)
    
    system_instruction = f"""
    You are DIRS AI, an expert Software Architect and technical document assistant. 
    You are helping the user analyze their uploaded documents.
    
    Here is the exact document data context you must use:
    {documents_context}
    
    Instructions:
    1. Answer the user's questions truthfully and precisely based ONLY on the provided document data context.
    2. If the user asks about something not mentioned in the documents, state politely: "I couldn't find details about that in the uploaded documents, but based on general knowledge..." or similar. Make it clear what is in the documents vs. what is external.
    3. Use clean markdown formatting (bold text, lists, code snippets) in your answers.
    4. Keep answers readable and professional.
    """
    
    contents = []
    
    for msg in payload.history:
        contents.append(
            {"role": "user" if msg.role == "user" else "model", "parts": [{"text": msg.content}]}
        )
        
    contents.append(
        {"role": "user", "parts": [{"text": payload.message}]}
    )
    
    try:
        from google.genai import types
        
        logger.info(f"Requesting chat response for query: '{payload.message[:40]}...'")
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4
            )
        )
        
        logger.info("Successfully received answer from Gemini.")
        return {"answer": response.text}
        
    except Exception as e:
        logger.error(f"Gemini API chat call failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Gemini API Error: {str(e)}"
        )

@app.post("/api/chat/stream")
async def chat_companion_stream(
    payload: ChatPayload,
    x_gemini_api_key: Optional[str] = Header(None)
):
    if not documents_store:
        raise HTTPException(status_code=400, detail="No documents available. Please upload files first.")
        
    client = get_gemini_client(x_gemini_api_key)
    
    full_text_list = []
    for filename, doc in documents_store.items():
        full_text_list.append(f"File: {filename}\nContent:\n{doc['text']}")
    documents_context = "\n\n=== DOCUMENT DATABASE ===\n\n" + "\n\n".join(full_text_list)
    
    system_instruction = f"""
    You are DIRS AI, an expert Software Architect and technical document assistant. 
    You are helping the user analyze their uploaded documents.
    
    Here is the exact document data context you must use:
    {documents_context}
    
    Instructions:
    1. Answer the user's questions truthfully and precisely based ONLY on the provided document data context.
    2. If the user asks about something not mentioned in the documents, state politely: "I couldn't find details about that in the uploaded documents, but based on general knowledge..." or similar. Make it clear what is in the documents vs. what is external.
    3. Use clean markdown formatting (bold text, lists, code snippets) in your answers.
    4. Keep answers readable and professional.
    """
    
    contents = []
    for msg in payload.history:
        contents.append(
            {"role": "user" if msg.role == "user" else "model", "parts": [{"text": msg.content}]}
        )
    contents.append(
        {"role": "user", "parts": [{"text": payload.message}]}
    )
    
    from google.genai import types

    async def event_generator():
        # Async streaming call - runs on the event loop instead of a
        # worker thread, avoiding the "client has been closed" crash that
        # happens when the sync httpx client is used across threads under
        # concurrent requests (e.g. chat + document analysis at once).
        try:
            response_stream = await client.aio.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4
                )
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            # The response has already started streaming by the time we get
            # here, so we can't raise an HTTPException anymore - instead we
            # yield a visible error message so the frontend doesn't hang
            # forever on the typing indicator.
            logger.error(f"Gemini API streaming chat call failed: {str(e)}")
            yield f"\n\n⚠️ **Error:** {str(e)}"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
    
@app.get("/{filename}")
async def get_static_file(filename: str):
    file_path = os.path.join("static", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse(status_code=404, content="File not found")

@app.get("/")
async def read_index():
    """Serves the main frontend page."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse(status_code=404, content="static/index.html not found.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    is_production = os.environ.get("NODE_ENV") == "production" or "PORT" in os.environ
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=not is_production)