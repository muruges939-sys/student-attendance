# Student Attendance Management System

## Backend setup
1. python -m venv venv, then activate it
2. pip install -r requirements.txt
3. Create MySQL database student_attendance_db and import database/schema.sql
4. Copy .env.example to .env and fill in your values
5. cd backend
6. python create_admin.py   (creates the first admin)
7. python app.py            (runs on http://127.0.0.1:5000)

Frontend should run on http://127.0.0.1:5500 (CORS is set for it).