import os
import io
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uvicorn
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pypdf import PdfReader
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pdf=insight-hub")
app= FastAPI(title= "PDF Insight Hub Server")
documents_store: Dict[str, Dict[str, Any]] = {}
CACHE_DIR = os.environ.get("CACHE_DIR", "document_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

class DashboardStats(BaseModel): 
    pageCount: int= Field(description= "Total pages of all uploaded documents combined")
    wordCount: int= Field(description= "Total word count of all uploaded documents combined")
    riskCount: int= Field(description= "Number of critical issues, warnings, or risks found")
    sentiment: str= Field(description= "Overall mood")

class TopicData(BaseModel):
    labels: List[str]= Field(description= "Top 5 core topics discussed in the files")
    values: List[float]= Field(description= "Relevance percentage score for each topic")

class SentimentBreakdown(BaseModel):
    labels: List[str]= Field(description= "Should be")
    values: List[float]= Field(description= "Percentage allocation for each sentiment type")

class Takeaway(BaseModel):
    type: str= Field(description= "Must be 'success', 'warning', or 'primary'")
    icon: str= Field(description= "Icon name from Lucide")
    text: str= Field(description= "A short takeaway summary sentence")

class AnalysisResult(BaseModel):
    summary: str= Field(description= "Detailed executive summary formatted in Markdown")
    stats: DashboardStats
    topics: TopicData
    sentimentBreakdown: SentimentBreakdown
    takeaways: List[Takeaway]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatPlayload(BaseModel):
    message: str
    history: List[ChatMessage]

def get_gemini_client(api_key_header: Optional[str]= None):
    api_key= api_key_header or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail= "Gemini API key is missing. Enter it in the dashboard UI"
        )
    from google import genai
    from google.genai import types
    return genai.Client(api_key=api_key)

@app.post("/api/upload")
async def upload_document(file: UploadFile= File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are allowed.")
    
    try:
        contents= await file.read()
        pdf_file= io.BytesIO(contents)

        reader= PdfReader(pdf_file)
        text= ""
        for page in reader.pages:
            page_text= page.extract_text()
            if page_text:
                text += page_text + "\n"

        page_count= len(reader.pages)
        word_count= len(text.split())

        documents_store[file.filename]={
            "text": text,
            "pages": page_count,
            "words": word_count,
            "size": len(contents)
        }
        save_to_cache(file.filename, text, page_count, word_count)

        logger.info(f"Processed PDF: {file.filename} ({page_count} pages)")
        return {
            "status": "success",
            "filename": file.filename,
            "page_count": page_count,
            "word_count": word_count
        }
    except Exception as e:
        raise HTTPException(status_code= 500, detail=f"Failed to parse PDF: {str(e)}")
    
@app.post("/api/clear")
async def clear_documents():
    documents_store.clear()
    for entry in os.listdir(CACHE_DIR):
        if entry.endswith(".txt") or entry.endswith(".meta"):
            os.remove(os.path.join(CACHE_DIR, entry))
    logger.info("Cleared document store")
    return {"status": "cleared"}

@app.post("/api/summary", response_model= AnalysisResult)
async def generate_summary(x_gemini_api_key: Optional[str]= Header(None)):
    if not documents_store:
        raise HTTPException(status_code=400, detail="Please upload a PDF first!")
    
    client= get_gemini_client(x_gemini_api_key)

    full_text_list= []
    total_pages= 0
    total_words= 0
    for filename, doc in documents_store.items():
        total_pages += doc["pages"]
        total_words += doc["words"]
        full_text_list.append(f"---FILE: {filename} ---\n{doc['text']}")
    documents_context= "\n\n".join(full_text_list)

    prompt= f"""
    You are DIRS AI. Analyze the following documents:
    {documents_context}

    Format the response strictly to the JSON schema.
    Ensure:
    - 'pageCount' stats property matches exactly {total_pages}.
    - 'wordCount' stats property matches exactly {total_words}.
    - Extract topics (0-100%).
    """

    try:

        import json
        from google.genai import types
        

        response= client.models.generate_content(
            model= 'gemini-2.5-flash',
            contents=prompt,
            config= types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema= AnalysisResult,
                temperature= 0.2
            )
        )
        return json.loads(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")
    
@app.post("/api/chat")
async def chat_companion(playload: ChatPlayload, x_gemini_api_key: Optional[str]= Header(None)):
    if not documents_store:
        raise HTTPException(status_code=400, detail="Please upload files first.")
    
    client= get_gemini_client(x_gemini_api_key)

    full_text= "\n\n".join([f"File: {name}\n{doc['text']}" for name, doc in documents_store.items()])
    
    system_instruction= f"""
    You are DIRS AI, an expert technical document assistant.
    Answer questions based ONLY on this context:
    {full_text}
    """

    contents=[]
    for msg in playload.history:
        role="user" if msg.role=="user" else "model"
        contents.append({
            "role": role,
            "parts":[{"text":msg.content}]
        })

    contents.append({
        "role":"user",
        "parts":[{"text": playload.message}]
    })

    try:
            from google.genai import types
            response= client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_instruction,
                temperature=0.4)
            )
            return {"answer": response.text}
    except Exception as e:
            logger.error(f"Gemini API Exception: {str(e)}")
            raise HTTPException(status_code=500, detail=f"AI Chat Error: {str(e)}")
        
@app.get("/{filename}")
async def get_static_file(filename: str):
    file_path= os.path.join("static", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse(status_code=404, content="File not found")

from fastapi.responses import StreamingResponse


def save_to_cache(filename: str, text: str, pages: int, words: int):
    meta_path = os.path.join(CACHE_DIR, f"{filename}.meta")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"{pages},{words}")

    text_path = os.path.join(CACHE_DIR, f"{filename}.txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)


def load_cache():
    if not os.path.exists(CACHE_DIR):
        return

    for file_name in os.listdir(CACHE_DIR):
        if not file_name.endswith(".txt"):
            continue

        filename = file_name[:-4]
        meta_path = os.path.join(CACHE_DIR, f"{filename}.meta")
        if not os.path.exists(meta_path):
            continue

        with open(meta_path, "r", encoding="utf-8") as f:
            pages, words = map(int, f.read().split(","))

        with open(os.path.join(CACHE_DIR, file_name), "r", encoding="utf-8") as f:
            text = f.read()

        documents_store[filename] = {"text": text, "pages": pages, "words": words}


load_cache()

@app.post("/api/chat/stream")
async def chat_stream(payload: ChatPlayload, x_gemini_api_key: Optional[str] = Header(None)):
    if not documents_store:
        raise HTTPException(status_code=400, detail="Please upload files first.")
        
    client = get_gemini_client(x_gemini_api_key)
    
    full_text = "\n\n".join([f"File: {name}\n{doc['text']}" for name, doc in documents_store.items()])
    system_instruction = f"""
    You are DIRS AI, an expert technical document assistant.
    Answer questions based ONLY on this context:
    {full_text}
    """
    
    contents = []
    for msg in payload.history:
        role = "user" if msg.role == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg.content}]
        })
    contents.append({
        "role": "user",
        "parts": [{"text": payload.message}]
    })
    
    try:
        from google.genai import types
        response_stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4
            )
        )
        
        def event_generator():
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text

        return StreamingResponse(event_generator(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Stream Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI Chat Stream Error: {str(e)}")

@app.get("/")
async def read_index():
    """Serves the main frontend page."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse(status_code=404, content="static/index.html not found.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    is_dev = "PORT" not in os.environ
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=is_dev)