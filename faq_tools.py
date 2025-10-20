import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
 
PDF_PATH = "FAQ_assessor_v1.1.pdf"

def get_faq_context(question):
    loader = PyPDFLoader(PDF_PATH)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        transport='rest'
    )
    db = FAISS.from_documents(chunks, embeddings)

    results = db.similarity_search(question, k=6)
    
    return "\n\n".join([r.page_content for r in results])