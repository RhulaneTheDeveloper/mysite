import base64
import math
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, url_for, session, redirect, flash,jsonify
from flask_session import Session
from flask_mysqldb import MySQL
from flask import send_file
import io
import MySQLdb.cursors
import re
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from datetime import date, timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError
from flask import make_response
from PIL import Image
import matplotlib.pyplot as plt
import io
import base64
import pdfkit

config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')


app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.secret_key = 'your_secret_key'

app.config['MYSQL_HOST'] = 'Kefiloe.mysql.pythonanywhere-services.com'
app.config['MYSQL_USER'] = 'Kefiloe'
app.config['MYSQL_PASSWORD'] = 'databasepassword'
app.config['MYSQL_DB'] = 'Kefiloe$cirsdatatwo'


mysql = MySQL(app)
from helpers import citizen, m_personnel,t_conditions,a_personnel


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/aboutUs.html', methods=['GET', 'POST'])
def aboutUs():
    return render_template('aboutUsPage.html')

@app.route('/contactUs.html', methods=['GET', 'POST'])
def contactUs():
    return render_template('contactPage.html')

def register_user(full_name, id_number, phone_number, email, password):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    hashed_password = generate_password_hash(password)

    if "@cirs.com" in email:
            role = 'maintenance_personnel'
            specialization = 'not set'  # Default specialization for maintenance personnel
            num_work_done = 0
    elif "@cirs.ac.za" in email:
            role = 'authority_personnel'
            specialization = None
            num_work_done = None
    else:
            role = 'citizen'

    cursor.execute(
            'INSERT INTO user (full_names, password, email, phone_number,id_no, user_role) VALUES (%s,%s, %s, %s, %s, %s)',
            (full_name, hashed_password, email, phone_number,id_number, role)
        )

    user_id = cursor.lastrowid

    # Insert into the respective subclass table
    if "@cirs.com" in email:  # If it's a maintenance personnel
        cursor.execute(
            'INSERT INTO maintenance_personnel (maintenance_personnel_id, assigned_role, specialization, availability) '
            'VALUES (%s, %s, %s, %s)',
            (user_id, 'maintenance', specialization, 'available')
        )
    elif "@cirs.ac.za" in email:
        cursor.execute(
            'INSERT INTO authority_personnel (auth_id) VALUES ( %s)',
            (user_id,)
        )
    else:  # If it's a citizen
        cursor.execute(
            'INSERT INTO citizen (citizen_id) VALUES ( %s)',
            (user_id,)
        )

    mysql.connection.commit()
    cursor.close()


@app.route('/track_ticket/<int:ticket_id>', methods=['GET'])
def track_ticket(ticket_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM ticket WHERE ticket_id = %s", (ticket_id,))
    ticket = cursor.fetchone()
    cursor.close()

    if not ticket:
        flash("Ticket not found!", "danger")
        return redirect(url_for('my_tickets'))

    # Encode image if it exists
    if ticket.get('image_data'):
        encoded = base64.b64encode(ticket['image_data']).decode('utf-8')
        ticket['image_base64'] = f"data:image/jpeg;base64,{encoded}"
    else:
        ticket['image_base64'] = None

    return render_template('track_ticket.html', ticket=ticket)

@app.route('/signInPage.html', methods=['GET', 'POST'])
def sign_in():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        account = get_user_by_email(email)
        if account and check_password_hash(account['password'], password):  # Hash passwords in real apps
            flash('Logged in successfully!')
            session['loggedin'] = True
            session['id'] = account['id']

            session['email'] = account['email']
            session['role'] = account['user_role']  # Store role in session
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))  # Redirect to dashboard

        else:
            msg = 'Incorrect email or password!'

    return render_template('signInPage.html', msg=msg)

@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        if session['role'] == 'citizen':
            return redirect(url_for('c_dashboard'))
        elif session['role'] == 'maintenance_personnel':
            return redirect(url_for('m_dashboard'))
        elif session['role'] == 'authority_personnel':
            return redirect(url_for('a_dashboard'))

    return redirect(url_for('sign_in'))

@app.route('/profile.html', methods=['GET', 'POST'])
def viewProfile():
    if 'loggedin' not in session:
        return redirect(url_for('sign_in'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        # Form submitted: update the profile
        full_names = request.form['full_names']
        phone_number = request.form['phone_number']
        username = request.form['email']

        # Update the database
        cursor.execute("""
            UPDATE user
            SET full_names = %s, phone_number = %s
            WHERE email = %s
        """, (full_names, phone_number, session['email']))
        mysql.connection.commit()

        # Update session info
        session['email'] = username
        cursor.execute("""
            SELECT full_names, phone_number, email
            FROM user
            WHERE email = %s
        """, (username,))
        profile = cursor.fetchone()
        session['profile'] = profile
        flash("Profile updated successfully!")

    else:
        # Initial load: fetch profile data
        cursor.execute("""
            SELECT full_names, phone_number, email
            FROM user
            WHERE email = %s
        """, (session['email'],))
        profile = cursor.fetchone()
        session['profile'] = profile

    cursor.close()
    return render_template('profile.html')

@app.route('/registerPage.html', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        lfullname = request.form['fullname']
        idnum = request.form['idnum']
        phonenum = request.form['phonenum']
        lemail = request.form['email']
        passwd = request.form['password']


        try:
            register_user(lfullname, idnum, phonenum, lemail, passwd)
            msg ='You have successfully registered!'
            return redirect(url_for('sign_in'))


        except MySQLdb.IntegrityError as e:
            if e.args[0] == 1062:
                error_message = str(e.args[1])  # the actual MySQL error message
                if "for key 'user.email'" in error_message:
                    msg = 'Email already used!'
                elif "for key 'user.phone_number'" in error_message:
                    msg = "That phone_number is used."
                else:
                    flash("Duplicate entry detected.", "danger")
                    msg = "Duplicate entry detected."
            else:
                flash("A database error occurred.", "danger")

    return render_template('registerPage.html', msg=msg)

def deleteProfile(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if the user is a Citizen
    cursor.execute("SELECT * FROM user WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    if user['user_role'] == 'citizen':
        # Delete from Citizen table
        cursor.execute("DELETE FROM citizen WHERE citizen_id = %s", (user_id,))



    else:
        # Maintenance personnel deletion

        cursor.execute("DELETE FROM maintenance_personnel WHERE maintenance_personnel_id = %s", (user_id,))

    cursor.execute("DELETE FROM user WHERE user_id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()
    return "profile deleted"


# ---------------------------
# Delete Profile Route
# ---------------------------
@app.route('/delete_profile', methods=['POST'])
def delete_profile_route():
    if 'loggedin' in session:
        user_id = session['id']
        role = session['role']

        deleteProfile(user_id)

        session.clear()
        flash("Your profile has been deleted.")
        return redirect(url_for('index'))

    return redirect(url_for('sign_in'))



def get_user_by_email(email):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT user_id as id, full_names, password, email, phone_number ,user_role FROM user WHERE email = %s
    """, ( email,))

    user = cursor.fetchone()
    cursor.close()
    return user

def getUser(u_id = None):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if u_id == None:
        u_id = session['id']
    cursor.execute("""
        SELECT * FROM user WHERE user_id = %s
    """, ( u_id,))
    user = cursor.fetchone()
    cursor.close()
    return user

@app.route('/logout.html', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('index'))

#======================================================================================================================
#Citizen
#======================================================================================================================

@app.route('/c_dashboard')
def c_dashboard():
    if 'loggedin' in session and session['role'] == 'citizen':
        return render_template('c_dashboard.html')
    return redirect(url_for('sign_in'))

@app.route('/reportIncident.html', methods=['GET', 'POST'])
def reportIssue():
    if 'loggedin' in session:
        if request.method == 'GET':
            return render_template('reportIncident.html')
    citizen.reportIssue()
    return redirect(url_for('my_tickets'))

@app.context_processor
def inject_notifications():
    user_id = session.get('id')
    if not user_id:
        # No user logged in → no notifications
        return {'unread_notifications': [], 'unread_count': 0}

    nots = citizen.get_unread_notifications()
    return {
        'unread_notifications': nots,
        'unread_count': len(nots)
    }

@app.route('/mark_notification_read/<int:notif_id>', methods=['POST'])
def mark_notification_read(notif_id):
    cursor = mysql.connection.cursor()
    cursor.execute(
      "UPDATE notification SET is_read = TRUE WHERE notification_id = %s",
      (notif_id,)
    )
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('c_dashboard'))  # or simply back to the same page


@app.route('/r_comfirm', methods=['GET', 'POST'])
def confirmIssue():
    if 'loggedin' in session:
        if request.method == 'POST':
            session['ticketData']=citizen.putInSess()
            ticket =citizen.checkIfReported()
            if ticket == None:
                reportIssue()
            else:
                return render_template('confirm_r.html',ticket=ticket,sticket=session['ticketData'])

    return redirect(url_for('my_tickets'))



@app.route('/viewReports.html',methods=['GET','POST'])
def view_reports():
    reports = citizen.view_reports()
    return render_template('viewReports.html', reports=reports)

@app.route('/viewAReport.html',methods=['GET','POST'])
def view_a_report():
    report =citizen.view_a_report();
    return render_template('viewAReport.html', report=report)

@app.route('/delete_incident', methods=['POST'])
def delete_incident():
    citizen.delete_incident()

    return redirect(url_for('view_reports'))  # or reload the page where incidents are shown

@app.route('/viewInsight.html')
def incident_summary():
    status_summary = citizen.incident_summary()
    return render_template('viewInsight.html', summary=status_summary)




@app.route('/tarck.html', methods=['GET', 'POST'])
def trackProgress():
    return redirect(url_for('track'))

@app.route('/my_tickets.html')
def my_tickets():
    mytickets = citizen.my_tickets()
    return render_template('my_tickets.html', tickets=mytickets)


@app.route('/comments', methods=['GET', 'POST'])
def comment():
    ticket_id = request.form.get('t_id')
    comments = citizen.getComments(ticket_id)
    return render_template('comments.html',comments = comments,ticket_id= ticket_id)

@app.route('/sendComments', methods=['GET', 'POST'])
def sendcomment():
    ticket_id = request.form.get('t_id')
    if request.method == 'POST':
        citizen.sendComment(ticket_id)

    comments = citizen.getComments(ticket_id)
    return render_template('comments.html',comments = comments,ticket_id= ticket_id)


@app.route('/download_insights', methods=['GET', 'POST'])
def download_insights():
    status_summary = citizen.incident_summary()

    rendered = render_template('viewInsight.html', summary=status_summary)

    # --- Generate PDF from string ---
    pdf = pdfkit.from_string(rendered, False, configuration=config)

    # --- Send as response ---
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=view_app_summary.pdf'
    return response


#======================================================================================================================
#Maintenance_Personnel
#======================================================================================================================
@app.route('/m_dashboard')
def m_dashboard():
    if 'loggedin' in session and session['role'] == 'maintenance_personnel':
        specialization = m_personnel.getCurrentPersonnell()['specialization']
        if specialization == 'not set':
            return redirect(url_for('setRole'))
        user_id = session['id']
        tickets_by_date = m_personnel.tickets_last_4_days(user_id)
        recent_tickets = m_personnel.get_recent_tickets(user_id)

        return render_template('m_dashboard.html',tickets_by_date=tickets_by_date,recent_tickets=recent_tickets)
    return redirect(url_for('sign_in'))


@app.route('/ticket_updater.html', methods=['GET', 'POST'])
def ticket_updater():
    theTickets=m_personnel.ticket_updater()
    if request.method == 'POST':
        if request.form['status'] == 'closed':
            ticket_id = request.form['ticket_id']
            return render_template('setProof.html', t_id=ticket_id)
        return redirect(url_for('ticket_updater'))

    return render_template('ticket_updater.html', theTickets=theTickets)

@app.route('/setRole',methods=['GET', 'POST'])
def setRole():
    if request.method == 'POST':
        m_personnel.setRole()
        return redirect(url_for('m_dashboard'))

    return render_template('set_role.html')

@app.route('/personelClosed')
def closed_tickets():
    mytickets = t_conditions.getPersonnelClosedTickets(session['id'])
    return render_template('closedTickets.html', theTickets=mytickets)

@app.route('/issuedReports.html', methods=['GET'])
def issued_reports():
    incidents = m_personnel.issued_reports()
    return render_template('issuedReports.html', incidents=incidents)


@app.route('/download_incidents_pdf')
def download_incidents_pdf():
    return m_personnel.download_incidents_pdf()


@app.route('/update_location', methods=['POST'])
def update_location():
    return m_personnel.update_location()


@app.route('/get_assistance/<int:ticket_id>', methods=['POST'])
def getAssistance(ticket_id):
    count = t_conditions.countTicketPersonnel(ticket_id)['counted']
    if count>5:
        message = "assistance limit reached"
    else:
        u_id=m_personnel.getAssistance(ticket_id)
        assist_personnel =  getUser(u_id)
        message = f"{assist_personnel['full_names']} is assigned to assist"

    flash(message)
    return redirect(url_for('ticket_updater'))

@app.route('/setProof', methods=['GET', 'POST'])
def setNewImage():
    ticket_id = request.form.get('t_id')
    m_personnel.updateTicketImage(ticket_id)
    return redirect(url_for('ticket_updater'))






#======================================================================================================================
#Authority_Personnel
#======================================================================================================================

@app.route('/a_dashboard')
def a_dashboard():
    if 'loggedin' in session and session['role'] == 'authority_personnel':
        return redirect(url_for('viewAppSummary'))
    return redirect(url_for('sign_in'))

##finish this
def get_reports(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM incident WHERE report_id = %s", (id,))
    reports = cursor.fetchone()
    return reports

@app.route('/p_tickets', methods=['GET', 'POST'])
def p_tickets():
    p_id = request.form.get('p_id')
    mytickets = a_personnel.getPersonnelTicket(p_id)
    return render_template('my_tickets.html', tickets=mytickets)

@app.route('/viewAppSummary.html')
def viewAppSummary():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ---- 1. Get counts for the pie chart from ticket statuses ----
    cursor.execute("""
        SELECT status, COUNT(*) AS count
        FROM ticket
        GROUP BY status
    """)
    ticket_counts = cursor.fetchall()

    # Initialize all status types with 0
    status_data = {
        'pending': 0,
        'assigned': 0,
        'in progress': 0,
        'resolved': 0,
        'closed': 0
    }

    # Update with actual values from DB
    for row in ticket_counts:
        status_data[row['status']] = row['count']

    # ---- 2. Optionally add other stats to pass (users, teams, etc.) ----
    cursor.execute("SELECT COUNT(*) AS count FROM user")
    users = cursor.fetchone()['count']


    cursor.execute("SELECT COUNT(*) AS count FROM maintenance_personnel")
    workers = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM citizen")
    citizens = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM incident")
    incidents = cursor.fetchone()['count']

    cursor.close()

    # ---- 3. Combine all stats ----
    stats = {
        'users': users,
        'workers': workers,
        'citizens': citizens,
        'incidents': incidents,
        'pending': status_data['pending'],
        'assigned': status_data['assigned'],
        'in progress': status_data['in progress'],
        'resolved': status_data['resolved'],
        'closed': status_data['closed']
    }

    return render_template('viewAppSummary.html', stats=stats)

@app.route('/downloadAppSummary')
def download_app_summary_pdf():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # --- Get all stats ---
    cursor.execute("""
        SELECT status, COUNT(*) AS count
        FROM ticket
        GROUP BY status
    """)
    ticket_counts = cursor.fetchall()

    status_data = {
        'pending': 0,
        'assigned': 0,
        'in progress': 0,
        'resolved': 0,
        'closed': 0
    }

    for row in ticket_counts:
        status_data[row['status']] = row['count']

    cursor.execute("SELECT COUNT(*) AS count FROM user")
    users = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM maintenance_personnel")
    workers = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM citizen")
    citizens = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM incident")
    incidents = cursor.fetchone()['count']

    cursor.close()

    stats = {
        'users': users,
        'workers': workers,
        'citizens': citizens,
        'incidents': incidents,
        'pending': status_data['pending'],
        'assigned': status_data['assigned'],
        'in progress': status_data['in progress'],
        'resolved': status_data['resolved'],
        'closed': status_data['closed']
    }

    # --- Render HTML to string ---
    rendered = render_template('viewAppSummary.html', stats=stats)

    # --- Generate PDF from string ---
    pdf = pdfkit.from_string(rendered, False, configuration=config)

    # --- Send as response ---
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=view_app_summary.pdf'
    return response


def durationCalculator(ticket_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT created_at FROM incident WHERE incident_id = (SELECT incident_id FROM ticket WHERE ticket_id = %s)", (ticket_id,))
    firstDate = cursor.fetchone()
    if firstDate is None:
        return "N/A"  # or raise an error

    cursor.execute("SELECT created_at FROM ticket WHERE ticket_id = %s", (ticket_id,))
    lastDate = cursor.fetchone()
    if lastDate is None:
        return "N/A"  # or raise an error

    start_time = firstDate['created_at']
    end_time = lastDate['created_at']

    duration_minutes = (end_time - start_time).total_seconds() / 60
    return round(duration_minutes)

@app.route('/admin_reports', methods=['GET'])
def admin_reports():
    if 'loggedin' not in session or session.get('role') != 'authority_personnel':
        flash("Unauthorized access", "danger")
        return redirect(url_for('sign_in'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get filter criteria from query params
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    assigned_team = request.args.get('assigned_team')

    # Build SQL query with filters
    query = """
        SELECT i.incident_id, i.category, i.description, t.status, i.created_at
        FROM incident i
        LEFT JOIN ticket t ON i.incident_id = t.incident_id
        WHERE 1=1
    """
    params = []
    title=""
    if status:
        query += " AND t.status = %s"
        params.append(status)
        title="Status: "+status
    if start_date:
        query += " AND i.created_at >= %s"
        params.append(start_date)
        title="Date: "+start_date
    if end_date:
        query += " AND i.created_at <= %s"
        params.append(end_date)
        title="Date: "+end_date
    if assigned_team:
        query += " AND t.ticket_id in (select ticket_id from ticket_personnel where  maintenance_personnel_id= %s)"
        params.append(assigned_team)
        title="Maintence ID: "+assigned_team

    query += " ORDER BY i.created_at DESC"

    cursor.execute(query, tuple(params))
    reports = cursor.fetchall()
    cursor.close()

    return render_template('admin_reports.html', reports=reports,title=title)


@app.route('/download_admin_report_pdf', methods=['POST'])
def download_admin_report_pdf():
    if 'loggedin' not in session or session.get('role') != 'authority_personnel':
        flash("Unauthorized access", "danger")
        return redirect(url_for('sign_in'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Retrieve filters from form (POST)
    status = request.form.get('status')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    assigned_team = request.form.get('assigned_team')

    query = """
        SELECT i.incident_id, i.category, i.description, t.status, i.created_at
        FROM incident i
        LEFT JOIN ticket t ON i.incident_id = t.incident_id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND t.status = %s"
        params.append(status)

    if start_date:
        query += " AND i.created_at >= %s"
        params.append(start_date)

    if end_date:
        query += " AND i.created_at <= %s"
        params.append(end_date)

    if assigned_team:
        query += """
            AND t.ticket_id IN (
                SELECT ticket_id FROM ticket_personnel WHERE maintenance_personnel_id = %s
            )
        """
        params.append(assigned_team)

    query += " ORDER BY i.created_at DESC"

    cursor.execute(query, tuple(params))
    reports = cursor.fetchall()
    cursor.close()

    # Render HTML from template
    html = render_template('admin_report_pdf_template.html', reports=reports)

    # Convert HTML to PDF
    pdf = pdfkit.from_string(html, False, configuration=config, options={
        'enable-local-file-access': ''
    })

    # Create response
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=admin_report.pdf'

    return response


if __name__ == '__main__':
    app.run(debug=True)
