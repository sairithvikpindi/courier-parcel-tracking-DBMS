
import streamlit as st
import sqlite3
import uuid
from datetime import datetime

DB = "courier.db"

# ---------------- DATABASE ----------------
def connect():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def initialize_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                tracking_no TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                weight REAL NOT NULL CHECK(weight > 0),
                service TEXT NOT NULL,
                charge REAL NOT NULL CHECK(charge > 0),
                status TEXT NOT NULL DEFAULT 'Booked',
                booked_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_no TEXT NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL,
                scan_time TEXT NOT NULL,
                FOREIGN KEY(tracking_no)
                    REFERENCES bookings(tracking_no)
            )
        """)


def fetch_all(sql, params=()):
    with connect() as con:
        cur = con.execute(sql, params)
        columns = [col[0] for col in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


initialize_db()

# ---------------- USER INTERFACE ----------------
st.set_page_config(page_title="Courier DBMS", page_icon="📦",
                   layout="wide")

st.title("📦 Courier Parcel Booking & Tracking System")
st.caption("DBMS Project | Python + Streamlit + SQLite")

# Dashboard metrics
bookings = fetch_all("SELECT * FROM bookings")
total = len(bookings)
delivered = sum(b["status"] == "Delivered" for b in bookings)
pending = total - delivered
revenue = sum(b["charge"] for b in bookings)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Parcels", total)
c2.metric("Delivered", delivered)
c3.metric("Not Delivered", pending)
c4.metric("Total Charges", f"₹{revenue:.2f}")

booking_tab, tracking_tab, update_tab, reports_tab = st.tabs([
    "📝 Book Parcel", "🔍 Track Parcel",
    "🚚 Update Delivery", "📊 Reports & SQL"
])

# ---------------- BOOKING ----------------
with booking_tab:
    st.subheader("Create a Parcel Booking")

    with st.form("booking_form"):
        sender = st.text_input("Sender Name")
        receiver = st.text_input("Receiver Name")
        weight = st.number_input(
            "Parcel Weight (kg)", min_value=0.1,
            max_value=100.0, value=1.0, step=0.1
        )
        service = st.selectbox(
            "Service Type", ["Standard", "Express"]
        )
        submitted = st.form_submit_button("Book Parcel")

    if submitted:
        if not sender.strip() or not receiver.strip():
            st.error("Enter both sender and receiver names.")
        else:
            # Example project pricing rules
            if service == "Standard":
                charge = 80 + weight * 40
            else:
                charge = 150 + weight * 60

            tracking = "TRK" + uuid.uuid4().hex[:8].upper()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                with connect() as con:
                    con.execute("""
                        INSERT INTO bookings
                        (tracking_no, sender, receiver, weight,
                         service, charge, status, booked_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (tracking, sender.strip(),
                          receiver.strip(), weight, service,
                          charge, "Booked", now))

                    con.execute("""
                        INSERT INTO scans
                        (tracking_no, location, status, scan_time)
                        VALUES (?, ?, ?, ?)
                    """, (tracking, "Booking Branch", "Booked", now))

                st.success("Parcel booked successfully!")
                st.code(f"Tracking Number: {tracking}")
                st.write(f"Calculated charge: ₹{charge:.2f}")
                st.info("Save the tracking number to track this parcel.")

            except sqlite3.Error as e:
                st.error(f"Database error: {e}")

# ---------------- TRACKING ----------------
with tracking_tab:
    st.subheader("Track Your Parcel")

    tracking_search = st.text_input(
        "Enter Tracking Number", key="tracking_search"
    )

    if st.button("Search Parcel"):
        result = fetch_all(
            "SELECT * FROM bookings WHERE tracking_no = ?",
            (tracking_search.strip().upper(),)
        )

        if result:
            parcel = result[0]
            st.success(f"Current Status: {parcel['status']}")

            a, b, c = st.columns(3)
            a.write(f"**Sender:** {parcel['sender']}")
            b.write(f"**Receiver:** {parcel['receiver']}")
            c.write(f"**Weight:** {parcel['weight']} kg")

            st.write(f"**Service:** {parcel['service']}")
            st.write(f"**Charge:** ₹{parcel['charge']:.2f}")
            st.write(f"**Booked At:** {parcel['booked_at']}")

            history = fetch_all("""
                SELECT location, status, scan_time
                FROM scans WHERE tracking_no = ?
                ORDER BY scan_time DESC, scan_id DESC
            """, (parcel["tracking_no"],))

            st.subheader("Tracking History")
            st.dataframe(history, use_container_width=True)
        else:
            st.warning("No parcel found. Check the tracking number.")

# ---------------- STATUS UPDATES ----------------
with update_tab:
    st.subheader("Record a Tracking Scan")

    all_parcels = fetch_all("""
        SELECT tracking_no, status FROM bookings
        ORDER BY booked_at DESC
    """)

    if all_parcels:
        selected = st.selectbox(
            "Select Parcel",
            all_parcels,
            format_func=lambda p:
                f"{p['tracking_no']} — {p['status']}"
        )

        location = st.text_input("Current Branch / Hub / Location")

        new_status = st.selectbox(
            "New Status",
            ["In Transit", "At Hub", "Out for Delivery",
             "Delivery Failed", "Delivered"]
        )

        if st.button("Save Tracking Update"):
            current = fetch_all(
                "SELECT status FROM bookings WHERE tracking_no = ?",
                (selected["tracking_no"],)
            )[0]["status"]

            if current == "Delivered":
                st.error("Delivered parcels cannot receive further scans.")
            elif not location.strip():
                st.error("Enter a location.")
            else:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with connect() as con:
                    con.execute("""
                        UPDATE bookings SET status = ?
                        WHERE tracking_no = ?
                    """, (new_status, selected["tracking_no"]))

                    con.execute("""
                        INSERT INTO scans
                        (tracking_no, location, status, scan_time)
                        VALUES (?, ?, ?, ?)
                    """, (selected["tracking_no"], location.strip(),
                          new_status, now))

                st.success("Tracking status and scan history updated.")
                st.rerun()
    else:
        st.info("Book a parcel first.")

# ---------------- REPORTS AND SQL ----------------
with reports_tab:
    st.subheader("All Parcel Records")

    all_bookings = fetch_all("""
        SELECT tracking_no, sender, receiver, weight,
               service, charge, status, booked_at
        FROM bookings ORDER BY booked_at DESC
    """)

    if all_bookings:
        st.dataframe(all_bookings, use_container_width=True)
    else:
        st.info("No bookings available yet.")

    st.subheader("Status-wise Parcel Summary")

    summary = fetch_all("""
        SELECT status, COUNT(*) AS parcel_count
        FROM bookings
        GROUP BY status
        ORDER BY parcel_count DESC
    """)

    if summary:
        st.dataframe(summary, use_container_width=True)

    st.subheader("Revenue by Service Type")

    revenue_report = fetch_all("""
        SELECT service,
               COUNT(*) AS total_bookings,
               ROUND(SUM(charge), 2) AS total_charges
        FROM bookings
        GROUP BY service
    """)

    if revenue_report:
        st.dataframe(revenue_report, use_container_width=True)

    st.subheader("SQL Demonstration")

    st.code("""
SELECT status, COUNT(*) AS parcel_count
FROM bookings
GROUP BY status;

SELECT b.tracking_no, b.receiver,
       s.location, s.status, s.scan_time
FROM bookings b
JOIN scans s
ON b.tracking_no = s.tracking_no
ORDER BY s.scan_time DESC;
""", language="sql")

    if st.button("Run JOIN Query"):
        join_results = fetch_all("""
            SELECT b.tracking_no, b.receiver,
                   s.location, s.status, s.scan_time
            FROM bookings b
            JOIN scans s
              ON b.tracking_no = s.tracking_no
            ORDER BY s.scan_time DESC
        """)
        st.dataframe(join_results, use_container_width=True)

st.divider()
st.caption("Academic demonstration | Courier Parcel DBMS")
