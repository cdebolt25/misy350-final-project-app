## Import libraries
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / "users.json"
EVENTS_FILE = BASE_DIR / "events.json"
PASSES_FILE = BASE_DIR / "passes.json"


def _load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

## Had some AI help here
def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# Load data
users = _load_json(USERS_FILE, [])
events = _load_json(EVENTS_FILE, [])
passes = _load_json(PASSES_FILE, [])


def save_users():
    _save_json(USERS_FILE, users)


def save_events():
    _save_json(EVENTS_FILE, events)


def save_passes():
    _save_json(PASSES_FILE, passes)


def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "nav" not in st.session_state:
        st.session_state.nav = "Login"


def logout():
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.nav = "Login"


def find_user_by_username(name: str):
    n = name.strip().lower()
    for u in users:
        if u["username"].lower() == n:
            return u
    return None


def need_remaining(need: dict) -> int:
    claimed = sum(c.get("quantity", 0) for c in need.get("contributions", []))
    return max(0, need["quantity_needed"] - claimed)


def event_by_id(eid: str):
    for e in events:
        if e["event_id"] == eid:
            return e
    return None


def chatbot_reply(message: str) -> str:
    low = message.strip().lower()

    ## Specific event questions and answers
    if "what can i bring" in low or "what should i bring" in low:
        for ev in events:
            if ev["title"].lower() in low:
                lines = []
                for need in ev.get("needs", []):
                    rem = need_remaining(need)
                    if rem > 0:
                        lines.append(f"• {need['description']} — still need **{rem}** (of {need['quantity_needed']})")
                if not lines:
                    return f"Everything on the needs list for **{ev['title']}** is fully covered. Thanks, community!"
                return (
                    f"For **{ev['title']}**, you could still contribute:\n\n"
                    + "\n".join(lines)
                )
        return (
            "Name the event in your question (use the exact title from the catalog), for example: "
            "*What can I bring to the Python Study Group?*"
        )

    ## Schedule questions and answers
    if "when" in low and "event" in low:
        if not events:
            return "No upcoming events are published yet. Check back soon!"
        ## Had some AI help here
        lines = [f"• **{e['title']}** — {e.get('datetime', 'TBD')} @ {e.get('location', 'TBD')}" for e in events]
        return "Here is what is on the calendar:\n\n" + "\n".join(lines)

    ## How to claim questions and answers
    if "how" in low and "claim" in low:
        return (
            "Go to **Discover & claim**, pick an event, choose an open need, and enter how many units you can bring. "
            "You will get a digital entry pass right away."
        )

    ## Simple greetings
    if low in ("hi", "hello", "hey") or low.startswith("hello ") or low.startswith("hi "):
        return "Hi! I am the Resource Assistant. Ask what you can bring to a specific event, how claiming works, or when events are scheduled."

    ## Starting point defautls
    return (
        "Try asking:\n"
        "- *What can I bring to the Python Study Group?* (use a real event title)\n"
        "- *How do I claim a need?*\n"
        "- *When are the events?*\n"
        "- Say *hello*"
    )

## UI setup
init_session()
st.set_page_config(page_title="Community Exchange MVP", layout="wide")
st.title("Community Exchange")
st.caption("Place holder for now - FIX LATER")

with st.sidebar:
    st.subheader("Navigation")
    if st.session_state.logged_in:
        st.write(f"Signed in as **{st.session_state.username}** ({st.session_state.role})")
        if st.session_state.role == "architect":
            nav = st.radio(
                "Go to",
                ["Architect hub", "Resource Assistant"],
                key="nav_arch",
            )
        else:
            nav = st.radio(
                "Go to",
                ["Discover & claim", "My entry passes", "Resource Assistant"],
                key="nav_col",
            )
        if st.button("Log out", type="primary"):
            logout()
            st.rerun()
    else:
        nav = st.radio("Go to", ["Login", "Register"], key="nav_guest")
        st.session_state.nav = nav

## Sidebar with session state
if st.session_state.logged_in:
    view = nav
else:
    view = nav


## Registration for guests
if not st.session_state.logged_in and view == "Register":
    st.header("Create an account")
    with st.form("register_form"):
        uname = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        role = st.selectbox("Role", ["collaborator", "architect"], format_func=lambda r: "Collaborator (attendee)" if r == "collaborator" else "Event Architect (admin)")
        submitted = st.form_submit_button("Register")
    if submitted:
        if not uname.strip() or not pw:
            st.error("Username and password are required.")
        elif pw != pw2:
            st.error("Passwords do not match.")
        elif find_user_by_username(uname):
            st.error("That username is already taken.")
        else:
            uid = new_id("USR")
            users.append(
                {
                    "user_id": uid,
                    "username": uname.strip(),
                    "password_hash": hash_password(pw),
                    "role": role,
                }
            )
            save_users()
            st.success("Account created. Switch to **Login** in the sidebar.")

## login for guestss
elif not st.session_state.logged_in and view == "Login":
    st.header("Log in")
    with st.form("login_form"):
        uname = st.text_input("Username", key="login_user")
        pw = st.text_input("Password", type="password", key="login_pw")
        go = st.form_submit_button("Log in")
    if go:
        u = find_user_by_username(uname)
        if u is None or u["password_hash"] != hash_password(pw):
            st.error("Invalid username or password.")
        else:
            st.session_state.logged_in = True
            st.session_state.user_id = u["user_id"]
            st.session_state.username = u["username"]
            st.session_state.role = u["role"]
            st.success("Welcome back!")
            st.rerun()
