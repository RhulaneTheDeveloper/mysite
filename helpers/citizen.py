import base64
import math
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, url_for, session, redirect, flash,jsonify
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
from . import  m_personnel, t_conditions


from app import mysql

sast = pytz.timezone('Africa/Johannesburg')
now = datetime.now(sast)

def reportIssue():

    if 'loggedin' in session:

        issue_type = request.form.get('issue_type', 'default_value')
        description = request.form.get('description', 'No discription')
        if request.method == 'GET':
            return render_template('reportIncident.html')
        elif request.method =='POST':
            user= get_user_by_email(session['email'])
            if user:
                report_Incident(email=user['email'],issue_type=issue_type,desc=description)

                flash("Successfully reported!")
                return redirect(url_for('my_tickets'))
    return redirect(url_for('view_reports'))

def report_Incident(email,issue_type,desc):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        creationdate = datetime.now(pytz.timezone("Africa/Johannesburg"))
        if not email:
            flash('Email not found. Please login again.', 'danger')
            return redirect(url_for('dashboard'))

        latitude = request.form.get('latitude', None)
        longitude = request.form.get('longitude', None)

        # Process image
        camera_image_data = request.form.get('cameraImage')
        uploaded_file = request.files.get('image')

        camera_image_blob = None

        if camera_image_data:
            # If camera image was captured
            header, encoded = camera_image_data.split(',', 1)
            camera_image_blob = base64.b64decode(encoded)
        elif uploaded_file and uploaded_file.filename != '':
            # Else if image was uploaded
            camera_image_blob = uploaded_file.read()

        # Latitude and Longitude to float if available
        latitude = float(latitude) if latitude else None
        longitude = float(longitude) if longitude else None



        nearest_personnell_id = nearest_personnell(issue_type,latitude,longitude)
        # Connect and call procedure


        cursor.callproc('reportIncidentAndTicket', [
            email,
            nearest_personnell_id,
            issue_type,
            desc,
            camera_image_blob,
            latitude,
            longitude,
            'pending',  # status hardcoded to pending
            creationdate
        ])
        incident_id = cursor.lastrowid



        cursor.execute(""" UPDATE ticket SET created_at = %s WHERE citizen_id = %s
        """, (creationdate ,incident_id))



        # Get inserted ids
        result = cursor.fetchall()
        if result:
            incident_id = result[0]['incident_id']
            ticket_id = result[0]['ticket_id']
            flash(f'Report submitted successfully! Incident ID: {incident_id}, Ticket ID: {ticket_id}', 'success')
        else:
            flash('Report submitted but IDs could not be retrieved.', 'warning')


        m_personnel.updateMStatus(nearest_personnell_id)
        mysql.connection.commit()
    except Exception as e:
        print(f"Error: {e}")
        flash('Failed to report issue.', 'danger')
    finally:
        cursor.close()
        mysql.connection.commit()


def putInSess():
    latitude = request.form.get('latitude', None)
    longitude = request.form.get('longitude', None)
    issue_type = request.form.get('issue_type', 'default_value')
    description = request.form.get('description', 'No discription')
    camera_image_data = request.form.get('cameraImage')

    sessTicket = {
        'lat': latitude,
        'lon': longitude,
        'img': camera_image_data,
        'i_t': issue_type,
        'des': description
    }
    return sessTicket

def checkIfReported():
    sessTicket = session.get('ticketData')
    issuetype = sessTicket['i_t']
    latitude = sessTicket['lat']
    longitude = sessTicket['lon']

    latitude = float(latitude) if latitude else None
    longitude = float(longitude) if longitude else None

    already_exists = testAssigned(issuetype,latitude, longitude)
    return already_exists


def nearest_personnell(issue_type,ticket_lat,ticket_lon):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    specialization = t_conditions.getSpecialization(issue_type)
    # Get all maintenance team locations
    cursor.execute("SELECT * FROM maintenance_personnel where specialization = %s",(specialization,))
    teams = cursor.fetchall()

    nearest_team_id = None
    min_distance = float('inf')

    for team in teams:
        # Parse team location
        if team['availability'] == 'available':

            team_lat_str, team_lon_str = team['location'].split(',')
            team_lat = float(team_lat_str.replace("Lat:", "").strip())
            team_lon = float(team_lon_str.replace("Lon:", "").strip())

        # Calculate distance using haversine
            dist = haversine(ticket_lat, ticket_lon, team_lat, team_lon)
            if dist < min_distance:
                min_distance = dist
                nearest_team_id = team['maintenance_personnel_id']

    if nearest_team_id is None:
            min_distance = float('inf')  # Reset distance for new search
            for team in teams:
                if team['availability'] == 'busy':
                    team_lat_str, team_lon_str = team['location'].split(',')
                    team_lat = float(team_lat_str.replace("Lat:", "").strip())
                    team_lon = float(team_lon_str.replace("Lon:", "").strip())

                    dist = haversine(ticket_lat, ticket_lon, team_lat, team_lon)
                    if dist < min_distance:
                        min_distance = dist
                        nearest_team_id = team['maintenance_personnel_id']


    cursor.close()
    return nearest_team_id


def view_reports():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        r_id=session['id']
        cursor.execute("SELECT * FROM incident WHERE citizen_id = %s", (r_id,))
        reports = cursor.fetchall()



        for report in reports:
            cursor.execute("SELECT ticket_id FROM ticket WHERE incident_id = %s", (report['incident_id'],))
            report['ticket_id'] = cursor.fetchone()['ticket_id']
            if report['image_data']:
                encoded = base64.b64encode(report['image_data']).decode('utf-8')
                report['image_base64'] = f"data:image/jpeg;base64,{encoded}"
            else:
                report['image_base64'] = None  # or set to a placeholder URL

        cursor.close()
        return reports


def view_a_report():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        r_id=request.form['incident_id']
        cursor.execute("SELECT * FROM incident WHERE incident_id = %s", (r_id,))
        report = cursor.fetchone()
        cursor.close()

        if report and report.get('location'):
            match = re.match(r'Lat:\s*(-?\d+\.\d+),\s*Lon:\s*(-?\d+\.\d+)', report['location'])
            if match:
                report['lat'] = float(match.group(1))
                report['lon'] = float(match.group(2))
            else:
                report['lat'], report['lon'] = None, None
        else:
            report['lat'], report['lon'] = None, None


        if report['image_data']:
            encoded = base64.b64encode(report['image_data']).decode('utf-8')
            report['image_base64'] = f"data:image/jpeg;base64,{encoded}"
        else:
            report['image_base64'] = None  # or set to a placeholder URL
        return report


def delete_incident():
    incident_id = request.form.get('incident_id')

    if not incident_id:
        flash('Invalid incident ID.', 'danger')
        return redirect(url_for('dashboard'))  # or wherever you want to go back

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cursor.execute("""
        select ticket_id from ticket where incident_id=%s
""", (incident_id,))

        t_id_row = cursor.fetchone()

        t_id = t_id_row['ticket_id']

        cursor.execute("SELECT maintenance_personnel_id FROM ticket_personnel WHERE ticket_id =  %s", (t_id,))
        m_id = cursor.fetchall()

        # Call the stored procedure
        cursor.callproc('DeleteIncidentByIdSimple', [incident_id])


        mysql.connection.commit()
        for mIds in m_id:
            m_personnel.updateMStatus(mIds['maintenance_personnel_id'])
            m = m_personnel.getCurrentPersonnell(mIds)
            m_personnel.assign(m)
        cursor.close()



        flash('Incident deleted successfully.', 'success')
    except Exception as e:
        print(e)
        flash('Error deleting incident.', 'danger')
  # or reload the page where incidents are shown


def incident_summary():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Get ticket counts per status including 0s
        cursor.execute("""
    SELECT s.status, COUNT(t.status) AS count
    FROM (
        SELECT CONVERT('pending' USING latin1) AS status UNION
        SELECT CONVERT('assigned' USING latin1) UNION
        SELECT CONVERT('in progress' USING latin1) UNION
        SELECT CONVERT('resolved' USING latin1) UNION
        SELECT CONVERT('closed' USING latin1)
    ) AS s
    LEFT JOIN ticket t ON s.status = t.status AND t.citizen_id = %s
    GROUP BY s.status
    ORDER BY FIELD(s.status, 'pending', 'assigned', 'in progress', 'resolved', 'closed')
""", (session['id'],))

        status_summary = cursor.fetchall()
        cursor.close()
        return status_summary





def trackProgress():
    return redirect(url_for('track'))


def my_tickets():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    r_id = session['id']
    cursor.execute("SELECT * FROM ticket WHERE citizen_id = %s", (r_id,))
    mytickets = cursor.fetchall()
    for ticket in mytickets:
        if ticket['image_data']:
            encoded = base64.b64encode(ticket['image_data']).decode('utf-8')
            ticket['image_base64'] = get_image_base64(ticket['image_data'])

        else:
            ticket['image_base64'] = None
        status = ticket['status']
        if status == 'closed':
            ticket['duration']= t_conditions.durationCalculator(ticket['ticket_id'])
        cursor.execute("SELECT created_at FROM incident WHERE incident_id = (SELECT incident_id FROM ticket WHERE ticket_id = %s)", (ticket['ticket_id'],))
        ticket['firstdate'] = cursor.fetchone()['created_at']
        ticket['maintenance_personnel_id'] = getTicketPersonnel(ticket['ticket_id'],)
    cursor.close()
    return mytickets

def get_image_base64(image_bytes):
    if not image_bytes:
        return None
    # Load image from bytes
    image = Image.open(io.BytesIO(image_bytes))
    # Get MIME type from format
    mime_type = Image.MIME.get(image.format, 'image/jpeg')  # fallback to jpeg if unknown
    # Encode to base64
    encoded = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{encoded}"


def haversine(lat1, lon1, lat2, lon2,R = 637.0):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c



def get_user_by_email(email):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT user_id as id, full_names, password, email, phone_number ,user_role FROM user WHERE email = %s
    """, ( email,))

    user = cursor.fetchone()
    cursor.close()
    return user



def testAssigned(issue_type,lat1, lon1,R=0.1):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT * FROM ticket where incident_type = %s
    """,(issue_type,))
    tickets = cursor.fetchall()
    nearest_ticket = None
    min_distance = float('inf')

    for team in tickets:
        # Parse team location
        if team['status'] != 'closed':

            team_lat_str, team_lon_str = team['location'].split(',')
            team_lat = float(team_lat_str.replace("Lat:", "").strip())
            team_lon = float(team_lon_str.replace("Lon:", "").strip())

        # Calculate distance using haversine
            dist = haversine(lat1, lon1, team_lat, team_lon,R)
            if dist < min_distance:
                min_distance = dist
                nearest_ticket = team

#    if nearest_ticket['image_data'] != None:
 #       encoded = base64.b64encode(nearest_ticket['image_data']).decode('utf-8')
 #       nearest_ticket['image_base64'] = get_image_base64(nearest_ticket['image_data'])
    return nearest_ticket;

def getTicketPersonnel(t_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT maintenance_personnel_id FROM ticket_personnel WHERE ticket_id =  %s", (t_id,))
    ticket_personnel_id = cursor.fetchall()
    cursor.close()
    return ticket_personnel_id

def getTicketReporterId(ticket):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
            SELECT citizen_id from incident where incident_id = %s
            """, (ticket['incident_id'],))
    c_id = cursor.fetchone()

    return c_id['citizen_id']

def get_unread_notifications():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
            SELECT * from notification where is_read = false and citizen_id = %s
            """, (session['id'],))
    nots = cursor.fetchall()
    return nots


def sendComment(ticket_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    creationdate = datetime.now(pytz.timezone("Africa/Johannesburg"))
    commentText = request.form.get('comment')
    cursor.execute(
        'INSERT INTO comment (ticket_id,user_id,comment_text,created_at) VALUES ( %s,%s,%s,%s)',
        (ticket_id,session['id'],commentText,creationdate)
    )
    mysql.connection.commit()

def getComments(ticket_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
            SELECT * from comment where ticket_id = %s
            """, (ticket_id,))
    results = cursor.fetchall()
    for result in results:
        cursor.execute("""
            SELECT full_names from user where user_id = %s
            """, (result['user_id'],))
        result['full_names'] = cursor.fetchone()['full_names']
    cursor.close()
    return results