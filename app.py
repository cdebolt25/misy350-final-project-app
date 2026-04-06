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
st.caption("Informational Meetings, Conferences, and More!")

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

## Hub or dashboard for architects (needed a little bit of help from online here)
elif st.session_state.logged_in and st.session_state.role == "architect" and view == "Architect hub":
    st.header("Event Architect hub")
    t1, t2 = st.tabs(["Events (create & manage)", "Needs lists (per event)"])

    with t1:
        st.subheader("Create event")
        with st.form("create_event"):
            title = st.text_input("Title")
            when = st.text_input("Date / time", placeholder="e.g. 2026-04-12 18:00")
            location = st.text_input("Location")
            desc = st.text_area("Description")
            c = st.form_submit_button("Create")
        if c:
            if not title.strip():
                st.error("Title is required.")
            else:
                events.append(
                    {
                        "event_id": new_id("EVT"),
                        "title": title.strip(),
                        "datetime": when.strip() or "TBD",
                        "location": location.strip() or "TBD",
                        "description": desc.strip(),
                        "needs": [],
                    }
                )
                save_events()
                st.success("Event created.")

        st.subheader("Read / update / delete events")
        if not events:
            st.info("No events yet. Create one above.")
        else:
            labels = [f"{e['title']} ({e['event_id']})" for e in events]
            idx = st.selectbox("Select event", range(len(labels)), format_func=lambda i: labels[i])
            ev = events[idx]
            with st.form("edit_event"):
                etitle = st.text_input("Title", value=ev["title"])
                ewhen = st.text_input("Date / time", value=ev["datetime"])
                eloc = st.text_input("Location", value=ev["location"])
                edesc = st.text_area("Description", value=ev["description"])
                colu, cold = st.columns(2)
                with colu:
                    upd = st.form_submit_button("Save changes")
                with cold:
                    dele = st.form_submit_button("Delete event")
                if upd:
                    ev["title"] = etitle.strip()
                    ev["datetime"] = ewhen.strip()
                    ev["location"] = eloc.strip()
                    ev["description"] = edesc.strip()
                    save_events()
                    st.success("Event updated.")
                if dele:
                    eid = ev["event_id"]
                    events.pop(idx)
                    passes[:] = [p for p in passes if p["event_id"] != eid]
                    save_events()
                    save_passes()
                    st.success("Event removed (related passes deleted).")
                    st.rerun()


    with t2:
        st.subheader("Maintain needs lists")
        if not events:
            st.warning("Create an event first.")
        else:
            names = [e["title"] for e in events]
            ei = st.selectbox("Event", range(len(names)), format_func=lambda i: names[i])
            ev = events[ei]

            st.markdown(f"**{ev['title']}** — {ev['datetime']} @ {ev['location']}")

            with st.form("add_need"):
                nd = st.text_input("Need description (e.g. 2 extension cords)")
                nq = st.number_input("Quantity needed", min_value=1, value=1, step=1)
                add = st.form_submit_button("Add need")
            if add:
                if not nd.strip():
                    st.error("Description required.")
                else:
                    ev.setdefault("needs", []).append(
                        {
                            "need_id": new_id("NED"),
                            "description": nd.strip(),
                            "quantity_needed": int(nq),
                            "contributions": [],
                        }
                    )
                    save_events()
                    st.success("Need added.")

            if not ev.get("needs"):
                st.info("No needs yet for this event.")
            else:
                for need in ev["needs"]:
                    rem = need_remaining(need)
                    with st.expander(f"{need['description']} — {rem} / {need['quantity_needed']} open"):
                        with st.form(f"need_{need['need_id']}"):
                            d2 = st.text_input("Description", value=need["description"], key=f"d_{need['need_id']}")
                            q2 = st.number_input(
                                "Quantity needed",
                                min_value=1,
                                value=int(need["quantity_needed"]),
                                key=f"q_{need['need_id']}",
                            )
                            c1, c2 = st.columns(2)
                            with c1:
                                save_need = st.form_submit_button("Save need")
                            with c2:
                                del_need = st.form_submit_button("Delete need")
                            if save_need:
                                need["description"] = d2.strip()
                                need["quantity_needed"] = int(q2)
                                save_events()
                                st.success("Need updated.")
                            if del_need:
                                nid = need["need_id"]
                                ev["needs"] = [n for n in ev["needs"] if n["need_id"] != nid]
                                passes[:] = [
                                    p for p in passes if not (p["event_id"] == ev["event_id"] and p["need_id"] == nid)
                                ]
                                save_events()
                                save_passes()
                                st.success("Need removed; related passes cleared.")
                                st.rerun()

## Collaborator discover events (not too bad but some help from online, still worked through everything myself)
elif st.session_state.logged_in and st.session_state.role == "collaborator" and view == "Discover & claim":
    st.header("Discover events & claim a contribution")
    if not events:
        st.info("No events published yet.")
    else:
        for ev in events:
            with st.expander(f"**{ev['title']}** — {ev['datetime']}"):
                st.write(ev.get("description", ""))
                st.caption(f"Location: {ev.get('location', 'TBD')}")
                open_needs = [n for n in ev.get("needs", []) if need_remaining(n) > 0]
                if not ev.get("needs"):
                    st.write("No needs listed.")
                elif not open_needs:
                    st.success("All needs are covered for this event.")
                else:
                    opts = [f"{n['description']} ({need_remaining(n)} open)" for n in open_needs]
                    choice = st.selectbox("Choose a need to sponsor", range(len(opts)), format_func=lambda i: opts[i], key=f"pick_{ev['event_id']}")
                    qty = st.number_input(
                        "How many units are you bringing?",
                        min_value=1,
                        max_value=need_remaining(open_needs[choice]),
                        key=f"qty_{ev['event_id']}",
                    )
                    if st.button("Claim & get entry pass", key=f"btn_{ev['event_id']}"):
                        need = open_needs[choice]
                        rem = need_remaining(need)
                        if qty > rem:
                            st.error("Not enough remaining for that need.")
                        else:
                            claim_id = new_id("CLM")
                            need.setdefault("contributions", []).append(
                                {
                                    "claim_id": claim_id,
                                    "user_id": st.session_state.user_id,
                                    "username": st.session_state.username,
                                    "quantity": int(qty),
                                }
                            )
                            pid = new_id("PASS")
                            passes.append(
                                {
                                    "pass_id": pid,
                                    "claim_id": claim_id,
                                    "user_id": st.session_state.user_id,
                                    "username": st.session_state.username,
                                    "event_id": ev["event_id"],
                                    "event_title": ev["title"],
                                    "need_id": need["need_id"],
                                    "need_description": need["description"],
                                    "quantity": int(qty),
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            save_events()
                            save_passes()
                            st.success(f"Pass **{pid}** issued. See **My entry passes**.")
                            st.balloons()

## Collaborator passes
elif st.session_state.logged_in and st.session_state.role == "collaborator" and view == "My entry passes":
    st.header("My entry passes")
    mine = [p for p in passes if p["user_id"] == st.session_state.user_id]
    if not mine:
        st.info("You have no passes yet. Claim a need from an event.")
    else:
        ## Needed help here, a lot of help haha
        for p in mine:
            with st.expander(f"{p['pass_id']} — {p['event_title']}"):
                st.write(f"**Contribution:** {p['need_description']} × {p['quantity']}")
                st.caption(f"Issued {p.get('created_at', '')}")
                if st.button("Cancel this contribution", key=f"cx_{p['pass_id']}"):
                    ev = event_by_id(p["event_id"])
                    cid = p.get("claim_id")
                    if ev:
                        for need in ev.get("needs", []):
                            if need["need_id"] == p["need_id"]:
                                if cid:
                                    need["contributions"] = [
                                        c for c in need.get("contributions", []) if c.get("claim_id") != cid
                                    ]
                                else:
                                    need["contributions"] = [
                                        c
                                        for c in need.get("contributions", [])
                                        if not (
                                            c["user_id"] == p["user_id"]
                                            and c["quantity"] == p["quantity"]
                                            and c.get("username") == p["username"]
                                        )
                                    ]
                                break
                    passes[:] = [x for x in passes if x["pass_id"] != p["pass_id"]]
                    save_events()
                    save_passes()
                    st.success("Contribution cancelled; pass removed.")
                    st.rerun()

## Resource Assistants
elif st.session_state.logged_in and view == "Resource Assistant":
    st.header("Resource Assistant (simulated)")
    st.caption("Hardcoded responses — Phase 1. Try the suggested questions.")
    q = st.text_input("Your question", placeholder='e.g. What can I bring to the Python Study Group?')
    if st.button("Ask"):
        if not q.strip():
            st.warning("Type a question first.")
        else:
            st.markdown(chatbot_reply(q))

else:
    st.info("Use the sidebar to log in or register.")
