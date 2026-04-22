"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path
from typing import Any

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# SQLite database path
DB_PATH = current_dir / "activities.db"

# Seed data used when the database is empty.
SEED_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply incremental schema migrations tracked by schema version."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY
        )
    """)

    applied_versions = {
        row["version"] for row in conn.execute("SELECT version FROM schema_migrations")
    }

    if 1 not in applied_versions:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK (max_participants > 0)
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS signups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                UNIQUE(activity_id, student_id),
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            );
        """)
        conn.execute("INSERT INTO schema_migrations(version) VALUES (1)")


def seed_data_if_empty(conn: sqlite3.Connection) -> None:
    activity_count = conn.execute("SELECT COUNT(*) AS count FROM activities").fetchone()["count"]
    if activity_count > 0:
        return

    for name, details in SEED_ACTIVITIES.items():
        conn.execute(
            """
            INSERT INTO activities(name, description, schedule, max_participants)
            VALUES (?, ?, ?, ?)
            """,
            (name, details["description"], details["schedule"], details["max_participants"]),
        )

    all_emails = {
        email
        for details in SEED_ACTIVITIES.values()
        for email in details["participants"]
    }
    for email in all_emails:
        conn.execute("INSERT INTO students(email) VALUES (?)", (email,))

    for activity_name, details in SEED_ACTIVITIES.items():
        for email in details["participants"]:
            conn.execute(
                """
                INSERT INTO signups(activity_id, student_id)
                SELECT activities.id, students.id
                FROM activities, students
                WHERE activities.name = ? AND students.email = ?
                """,
                (activity_name, email),
            )


def get_activities_from_db(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, name, description, schedule, max_participants
        FROM activities
        ORDER BY name
        """
    ).fetchall()

    activities = {
        row["name"]: {
            "description": row["description"],
            "schedule": row["schedule"],
            "max_participants": row["max_participants"],
            "participants": [],
        }
        for row in rows
    }

    participant_rows = conn.execute(
        """
        SELECT activities.name AS activity_name, students.email AS student_email
        FROM signups
        JOIN activities ON activities.id = signups.activity_id
        JOIN students ON students.id = signups.student_id
        ORDER BY activities.name, students.email
        """
    ).fetchall()

    for row in participant_rows:
        activities[row["activity_name"]]["participants"].append(row["student_email"])

    return activities


@app.on_event("startup")
def startup() -> None:
    with get_connection() as conn:
        run_migrations(conn)
        seed_data_if_empty(conn)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with get_connection() as conn:
        return get_activities_from_db(conn)


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    with get_connection() as conn:
        activity = conn.execute(
            "SELECT id, max_participants FROM activities WHERE name = ?",
            (activity_name,),
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        student = conn.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()
        if student is None:
            cursor = conn.execute("INSERT INTO students(email) VALUES (?)", (email,))
            student_id = cursor.lastrowid
        else:
            student_id = student["id"]

        existing_signup = conn.execute(
            "SELECT 1 FROM signups WHERE activity_id = ? AND student_id = ?",
            (activity["id"], student_id),
        ).fetchone()
        if existing_signup is not None:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up"
            )

        signup_count = conn.execute(
            "SELECT COUNT(*) AS count FROM signups WHERE activity_id = ?",
            (activity["id"],),
        ).fetchone()["count"]
        if signup_count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is already full")

        conn.execute(
            "INSERT INTO signups(activity_id, student_id) VALUES (?, ?)",
            (activity["id"], student_id),
        )

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    with get_connection() as conn:
        activity = conn.execute(
            "SELECT id FROM activities WHERE name = ?",
            (activity_name,),
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        student = conn.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()
        if student is None:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        cursor = conn.execute(
            "DELETE FROM signups WHERE activity_id = ? AND student_id = ?",
            (activity["id"], student["id"]),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

    return {"message": f"Unregistered {email} from {activity_name}"}
