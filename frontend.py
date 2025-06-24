import streamlit as st
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from app.db import SessionLocal, engine
from app.models import Base, User, Document, ChatHistory
from app.utils import hash_password, verify_password
from app.embedding import chunk_text, get_embedding
from app.mistral_api import ask_mistral
import fitz  # PyMuPDF
import pandas as pd
import os
import tempfile
from datetime import datetime
from typing import List

# Initialize database
def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

init_db()

# Session state management
def init_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

init_session_state()

# Database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication functions
def signup(email: str, password: str):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            return False, "Email already registered."
        user = User(email=email, hashed_password=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return True, "User created successfully."
    except Exception as e:
        return False, str(e)
    finally:
        db.close()

def login(email: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            return False, None, "Invalid credentials"

        st.session_state.authenticated = True
        st.session_state.current_user = user
        st.session_state.chat_history = get_chat_history()
        return True, user, "Login successful"
    except Exception as e:
        return False, None, str(e)
    finally:
        db.close()

# Document processing
def ingest_file(file, filename):
    db = SessionLocal()
    try:
        ext = filename.lower().split(".")[-1]
        text = ""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name
        try:
            if ext == "txt":
                with open(tmp_path, "r", encoding="utf-8") as f:
                    text = f.read()
            elif ext == "pdf":
                doc = fitz.open(tmp_path)
                for page in doc:
                    text += page.get_text()
            elif ext == "csv":
                df = pd.read_csv(tmp_path)
                text = df.astype(str).apply(" ".join, axis=1).str.cat(sep=" ")
            else:
                os.remove(tmp_path)
                return False, "Unsupported file type"
        except Exception as e:
            os.remove(tmp_path)
            return False, str(e)
        os.remove(tmp_path)

        chunks = chunk_text(text)
        for chunk in chunks:
            embedding = get_embedding(chunk).tolist()
            db.add(Document(
                chunk=chunk,
                embedding=embedding,
                source=filename,
                user_id=st.session_state.current_user.id
            ))

        db.commit()
        return True, f"{filename} ingested successfully."
    except Exception as e:
        return False, str(e)
    finally:
        db.close()

# Question answering
def ask_question(query: str):
    db = SessionLocal()
    try:
        query_vector = get_embedding(query).tolist()
        stmt = (
            select(Document)
            .filter(Document.user_id == st.session_state.current_user.id)
            .order_by(Document.embedding.l2_distance(query_vector))
            .limit(3)
        )
        top_docs = db.execute(stmt).scalars().all()

        if not top_docs:
            answer = "No relevant information found in your documents."
        else:
            top_chunks = [doc.chunk for doc in top_docs]
            answer = ask_mistral(query, top_chunks)

        chat = ChatHistory(
            question=query,
            answer=answer,
            user_id=st.session_state.current_user.id
        )
        db.add(chat)
        db.commit()

        return answer
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def get_chat_history():
    db = SessionLocal()
    try:
        history = db.query(ChatHistory).filter(
            ChatHistory.user_id == st.session_state.current_user.id
        ).order_by(ChatHistory.id.desc()).all()
        return [{
            "id": h.id,
            "question": h.question,
            "answer": h.answer,
            "timestamp": "N/A"
        } for h in history]
    except Exception as e:
        return []
    finally:
        db.close()

def get_document_sources():
    db = SessionLocal()
    try:
        sources = db.query(Document.source).filter(
            Document.user_id == st.session_state.current_user.id
        ).distinct().all()
        return [s[0] for s in sources]
    except Exception as e:
        return []
    finally:
        db.close()

def delete_documents_by_source(source: str):
    db = SessionLocal()
    try:
        deleted_count = (
            db.query(Document)
            .filter(
                Document.user_id == st.session_state.current_user.id,
                Document.source == source
            )
            .delete()
        )
        db.commit()
        return deleted_count
    except Exception as e:
        return 0
    finally:
        db.close()

def delete_chat_history(history_ids: List[int]):
    db = SessionLocal()
    try:
        if not history_ids:
            return 0
        deleted_count = db.query(ChatHistory).filter(
            ChatHistory.id.in_(history_ids),
            ChatHistory.user_id == st.session_state.current_user.id
        ).delete(synchronize_session='fetch')
        db.commit()
        return deleted_count
    except Exception as e:
        print(f"Error deleting chat history: {e}")
        return 0
    finally:
        db.close()

# Streamlit UI
def main():
    st.title("Document Chat Assistant")

    if not st.session_state.authenticated:
        auth_tab, register_tab = st.tabs(["Login", "Register"])
        with auth_tab:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")
            if submit:
                success, user, message = login(email, password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

        with register_tab:
            with st.form("register_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                submit = st.form_submit_button("Register")
            if submit:
                if password != confirm_password:
                    st.error("Passwords don't match")
                else:
                    success, message = signup(email, password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

    else:
        st.sidebar.title(f"Welcome, {st.session_state.current_user.email}")
        if st.sidebar.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.session_state.chat_history = []
            st.rerun()

        with st.expander("Upload Documents"):
            uploaded_file = st.file_uploader("Choose a file (PDF, TXT, CSV)", type=["pdf", "txt", "csv"])
            if uploaded_file is not None:
                status, message = ingest_file(uploaded_file, uploaded_file.name)
                if status:
                    st.success(message)
                else:
                    st.error(message)

        with st.expander("Manage Documents"):
            sources = get_document_sources()
            if sources:
                selected_source = st.selectbox("Select document to delete", sources)
                if st.button("Delete Document"):
                    deleted_count = delete_documents_by_source(selected_source)
                    if deleted_count > 0:
                        st.success(f"Deleted {deleted_count} chunks from {selected_source}")
                        st.rerun()
                    else:
                        st.error("No documents found or error occurred")
            else:
                st.info("No documents uploaded yet")

        st.header("Chat with your documents")

        if len(st.session_state.chat_history) > 0:
            message_ids = {}
            for chat in st.session_state.chat_history:
                col1, col2 = st.columns([0.1, 0.9])
                message_ids[id(col1)] = chat["id"]
                with col1:
                    checkbox = st.checkbox("Select", key=f"checkbox-{chat['id']}")
                with col2:
                    with st.chat_message("user"):
                        st.write(chat["question"])
                    with st.chat_message("assistant"):
                        st.write(chat["answer"])
                    st.caption(chat["timestamp"])
                    st.divider()

            if st.button("Clear Selected Chat History"):
                selected_messages = []
                for key, chat_id in message_ids.items():
                    if st.session_state.get(f"checkbox-{chat_id}", False):
                        selected_messages.append(chat_id)
                if selected_messages:
                    deleted_count = delete_chat_history(selected_messages)
                    if deleted_count > 0:
                        st.success(f"Deleted {deleted_count} chat history entries.")
                        st.session_state.chat_history = [chat for chat in st.session_state.chat_history if chat["id"] not in selected_messages]
                    else:
                        st.error("No chat history found or error occurred.")
                else:
                    st.warning("Please select chat history entries to delete.")
        else:
            st.caption("No chat history")

        if prompt := st.chat_input("Ask a question about your documents"):
            new_message = {
                "id": max(item['id'] for item in st.session_state.chat_history) + 1 if st.session_state.chat_history else 1,
                "question": prompt,
                "answer": "",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.chat_history.insert(0, new_message)
            response = ask_question(prompt)
            st.session_state.chat_history[0]["answer"] = response
            st.rerun()

if __name__ == "__main__":
    main()
