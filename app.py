import os
import sqlite3
from datetime import datetime
import cv2
import numpy as np
import streamlit as st
from deepface import DeepFace

# ----------------- PAGE CONFIGURATION -----------------
st.set_page_config(page_title="AI Attendance System", layout="wide")
st.title("🎓 AI Attendance & Proctoring Portal")

DB_DIR = "db_faces"
DB_NAME = "attendance.db"
os.makedirs(DB_DIR, exist_ok=True)

# ----------------- DATABASE INITIALIZATION -----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students 
                 (student_id TEXT PRIMARY KEY, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Cache heavy AI model initialization in RAM across user clicks
@st.cache_resource
def prewarm_deepface():
    try:
        DeepFace.build_model("VGG-Face")
    except Exception:
        pass

prewarm_deepface()

# ----------------- NAVIGATION -----------------
menu = st.sidebar.selectbox("Navigation Panel", ["Register Face", "Verify Attendance", "View Attendance Logs"])

# ----------------- SECTION 1: REGISTER -----------------
if menu == "Register Face":
    st.subheader("📸 Register New Student")
    student_id = st.text_input("Student ID (e.g., ST-1001)")
    name = st.text_input("Full Name")
    img_file = st.camera_input("Capture Reference Face")

    if st.button("Save Registration"):
        if student_id and name and img_file:
            file_path = os.path.join(DB_DIR, f"{student_id}.jpg")
            bytes_data = img_file.getvalue()
            with open(file_path, "wb") as f:
                f.write(bytes_data)

            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO students VALUES (?, ?)", (student_id, name))
            conn.commit()
            conn.close()

            st.success(f"Registered student: {name} ({student_id})")
        else:
            st.error("Please provide Student ID, Name, and capture a photo.")

# ----------------- SECTION 2: VERIFY -----------------
elif menu == "Verify Attendance":
    st.subheader("✅ Verify Live Attendance")
    student_id = st.text_input("Enter Student ID to Verify")
    img_file = st.camera_input("Capture Live Verification Photo")

    if st.button("Verify Face & Mark Attendance"):
        registered_path = os.path.join(DB_DIR, f"{student_id}.jpg")
        
        if not os.path.exists(registered_path):
            st.error("Student ID not found. Please register first.")
        elif img_file and student_id:
            temp_path = os.path.join(DB_DIR, f"temp_{student_id}.jpg")
            with open(temp_path, "wb") as f:
                f.write(img_file.getvalue())

            st.info("Running DeepFace recognition...")
            try:
                result = DeepFace.verify(
                    img1_path=temp_path,
                    img2_path=registered_path,
                    detector_backend='opencv',
                    enforce_detection=False
                )
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)

                if result["verified"]:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute("INSERT INTO attendance (student_id, timestamp) VALUES (?, ?)", (student_id, timestamp))
                    conn.commit()
                    conn.close()

                    st.success(f"Verified! Attendance marked at {timestamp} (Distance: {result['distance']:.3f})")
                else:
                    st.error(f"Verification Failed! Face mismatch (Distance: {result['distance']:.3f})")

            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                st.error(f"Error during verification: {e}")

# ----------------- SECTION 3: LOGS -----------------
elif menu == "View Attendance Logs":
    st.subheader("📊 Historical Attendance Records")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT a.id, s.student_id, s.name, a.timestamp 
        FROM attendance a 
        JOIN students s ON a.student_id = s.student_id 
        ORDER BY a.id DESC
    """)
    logs = c.fetchall()
    conn.close()

    if logs:
        st.dataframe(
            logs, 
            column_config={"0": "Log ID", "1": "Student ID", "2": "Full Name", "3": "Timestamp"}, 
            use_container_width=True
        )
    else:
        st.info("No attendance logs recorded yet.")