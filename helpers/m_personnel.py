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
from helpers import citizen, m_personnel, t_conditions
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

from app import mysql




def tickets_last_4_days(maintenance_personnel_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)


    query = """
        SELECT DATE(t.created_at) AS report_date, COUNT(*) AS total_tickets
        FROM ticket t
        JOIN ticket_personnel tp ON t.ticket_id = tp.ticket_id
        WHERE t.created_at >= CURDATE() - INTERVAL 3 DAY
          AND tp.maintenance_personnel_id = %s
        GROUP BY DATE(t.created_at)
        ORDER BY report_date;

    """
    cursor.execute(query,(maintenance_personnel_id,))
    fetched = cursor.fetchall()

    # Initialize with 0 for each of the past 4 days
    today = date.today()
    result = {
        (today - timedelta(days=i)).strftime('%Y-%m-%d'): 0
        for i in range(3, -1, -1)
    }

    for row in fetched:
        result[row['report_date'].strftime('%Y-%m-%d')] = row['total_tickets']

    cursor.close()
    return result

def get_recent_tickets(maintenance_personnel_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Step 1: Get the team_id of the current maintenance personnel


    # Step 2: Get 3 most recent tickets for this team (using ticket.team_id directly)
    cursor.execute("""
    SELECT t.*
    FROM ticket t
    JOIN ticket_personnel tp ON t.ticket_id = tp.ticket_id
    WHERE tp.maintenance_personnel_id = %s
    ORDER BY t.created_at DESC
    LIMIT 3;
""", (maintenance_personnel_id,))

    recent_tickets = cursor.fetchall()
    cursor.close()
    return recent_tickets

def ticket_updater():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if 'loggedin' in session and session['role'] == 'maintenance_personnel':

        if request.method == 'POST':
            # Form submitted: update ticket status
            status = request.form['status']
            ticket_id = request.form['ticket_id']

            # Update the status in the database
            cursor.execute("""
                UPDATE ticket
                SET status = %s
                WHERE ticket_id = %s
            """, (status, ticket_id))


            #making personnel available after he closes a ticket
            if status == 'closed':
                ticket_personnel_id = citizen.getTicketPersonnel(ticket_id)
                for ids in ticket_personnel_id:
                    m_id = ids['maintenance_personnel_id']

                    cursor.execute("""
                    UPDATE maintenance_personnel
                    SET availability = 'busy'
                    WHERE maintenance_personnel_id = %s
                """, (m_id,))

                    cursor.execute("""
                    SELECT COUNT(a.ticket_id)
                    FROM ticket_personnel a
                    JOIN ticket b ON a.ticket_id = b.ticket_id
                    WHERE a.maintenance_personnel_id = %s
                      AND b.status != 'closed'
                """, (m_id,))
                    counter = cursor.fetchone()
                    ticket_count = list(counter.values())[0]
                    if ticket_count == 0:
                        cursor.execute("""
                        UPDATE maintenance_personnel
                        SET availability = 'available'
                        WHERE maintenance_personnel_id = %s
                    """, (m_id,))


                    now = datetime.now(pytz.timezone("Africa/Johannesburg"))

                    cursor.execute("""
                    UPDATE ticket
                    SET created_at = %s
                    WHERE ticket_id = %s
                """, (now, ticket_id))
                    m = getCurrentPersonnell(m_id)
                    assign(m,)
                send_notification(ticket_id)

            mysql.connection.commit()
            # Optional: flash message or redirect to avoid form re-submission
            return redirect(url_for('ticket_updater'))

        else:
            # GET request: render ticket list for manager
            cursor.execute("""
            SELECT a.*,b.maintenance_personnel_id
            FROM ticket a
            JOIN ticket_personnel b ON a.ticket_id = b.ticket_id
            WHERE b.maintenance_personnel_id = %s AND a.status != 'closed'
            """, (session['id'],))

            theTickets = cursor.fetchall()
            for ticket in theTickets:
                if ticket['image_data']:
                    encoded = base64.b64encode(ticket['image_data']).decode('utf-8')
                    ticket['image_base64'] = citizen.get_image_base64(ticket['image_data'])

            return theTickets

    return redirect(url_for('m_dashboard'))


def issued_reports():


    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""SELECT * FROM incident where
    incident_id in(select incident_id from ticket where
    ticket_id in (select ticket_id from ticket_personnel where maintenance_personnel_id = %s))""",(session['id'],))
    incidents = cursor.fetchall()
    cursor.close()

    return  incidents


def download_incidents_pdf():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM incident")
    incidents = cursor.fetchall()
    cursor.close()

    # Render the HTML from your template
    rendered_html = render_template('issuedReports.html', incidents=incidents)

    # Convert to PDF
    pdf = pdfkit.from_string(rendered_html, False, configuration=config)

    # Return as downloadable file
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=incident_report.pdf'
    return response


def update_location():

    data = request.get_json()
    lat = data.get('latitude')
    lon = data.get('longitude')

    if lat is None or lon is None:
        return jsonify({'error': 'Invalid data'}), 400

    location = f"{lat},{lon}"
    print(f"Updating location to: {location} for user ID: {session['id']}")

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE maintenance_personnel SET location=%s  WHERE maintenance_personnel_id=%s",
                   (location, session['id']))
    mysql.connection.commit()
    cursor.close()
    return jsonify({'message': 'Location updated'}), 200


def getAssistance(ticket_id):

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get location from ticket
    #cursor.execute("SELECT location FROM ticket WHERE ticket_id = %s", (ticket_id,))

    cursor.execute("""SELECT i.category as category, i.location as location
                    FROM ticket t
                    JOIN incident i ON t.incident_id = i.incident_id
                    WHERE t.ticket_id = %s
                    """, (ticket_id,))
    result = cursor.fetchone()
    location = result['location']
    category = result['category']

    specialization = t_conditions.getSpecialization(category)

    # Extract latitude and longitude from string: "Lat: x, Lon: y"
    parts = location.split(',')
    lat = float(parts[0].replace("Lat:", "").strip())
    lon = float(parts[1].replace("Lon:", "").strip())

    nearest_personnell_id = nearest_assist_personnell(ticket_id,specialization,lat,lon)


    # Assign if someone is found
    if nearest_personnell_id:
        cursor.execute("""
            INSERT INTO ticket_personnel (ticket_id, maintenance_personnel_id)
            VALUES (%s, %s)
        """, (ticket_id, nearest_personnell_id))
        mysql.connection.commit()

    updateMStatus(nearest_personnell_id)

    cursor.close()
    return nearest_personnell_id


def nearest_assist_personnell(ticket_id,specialization, ticket_lat, ticket_lon):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get available personnel not already assigned to this ticket
    cursor.execute("""
        SELECT * FROM maintenance_personnel
        WHERE availability = 'available'
        AND (specialization = %s OR specialization = 'general')
       AND maintenance_personnel_id NOT IN (
            SELECT maintenance_personnel_id
            FROM ticket_personnel
            WHERE ticket_id = %s
        )
    """, (specialization,ticket_id,))

    personnel_list = cursor.fetchall()

    nearest_team_id = None
    min_distance = float('inf')

    for team in personnel_list:
        try:
            team_lat_str, team_lon_str = team['location'].split(',')
            team_lat = float(team_lat_str.replace("Lat:", "").strip())
            team_lon = float(team_lon_str.replace("Lon:", "").strip())
        except:
            continue  # Skip if location format is bad

        dist = haversine(ticket_lat, ticket_lon, team_lat, team_lon)
        if dist < min_distance:
            min_distance = dist
            nearest_team_id = team['maintenance_personnel_id']

    cursor.close()
    return nearest_team_id

def haversine(lat1, lon1, lat2, lon2):
    R = 637.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def updateMStatus(nearest_personnell_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
                SELECT COUNT(a.ticket_id)
                FROM ticket_personnel a
                JOIN ticket b ON a.ticket_id = b.ticket_id
                WHERE a.maintenance_personnel_id = %s
                  AND b.status != 'closed'
            """, (nearest_personnell_id,))
    counter = cursor.fetchone()
    ticket_count = list(counter.values())[0]
    if ticket_count == 0:
        cursor.execute("""
            UPDATE maintenance_personnel
            SET availability = 'available'
            WHERE maintenance_personnel_id = %s
        """, (nearest_personnell_id,))
    else:
        cursor.execute("""
            UPDATE maintenance_personnel
            SET availability = 'unavailable'
            WHERE maintenance_personnel_id = %s
        """, (nearest_personnell_id,))
    cursor.close()

    mysql.connection.commit()

def getUnassigned():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
            SELECT *
            FROM ticket
            WHERE ticket_id NOT IN (
                SELECT ticket_id FROM ticket_personnel
            )""")

    results = cursor.fetchall()
    cursor.close()

    return results

def getNearestUnassigned(lat1, lon1,R=100):

    tickets=getUnassigned()
    nearest_ticket = None
    min_distance = float('inf')

    for team in tickets:
        # Parse team location
        if team['status'] != 'closed':

            team_lat_str, team_lon_str = team['location'].split(',')
            team_lat = float(team_lat_str.replace("Lat:", "").strip())
            team_lon = float(team_lon_str.replace("Lon:", "").strip())

        # Calculate distance using haversine
            dist = haversine(lat1, lon1, team_lat, team_lon)
            if dist < min_distance:
                min_distance = dist
                nearest_ticket = team

    return nearest_ticket;

def assign(m = None):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if m is None:
        m = getCurrentPersonnell()
    team_lat_str, team_lon_str= m['location'].split(',')
    team_lat = float(team_lat_str.replace("Lat:", "").strip())
    team_lon = float(team_lon_str.replace("Lon:", "").strip())
    ticket = getNearestUnassigned(team_lat, team_lon)
    if ticket is None:
        return "No unassigned tickets available"
    else:
        cursor.execute("""
            INSERT INTO ticket_personnel (ticket_id, maintenance_personnel_id)
            VALUES (%s, %s)
        """, (ticket['ticket_id'], m['maintenance_personnel_id']))
        mysql.connection.commit()
        cursor.close()

def setRole(m_id=None):
    if m_id is None:
        m_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    specialization = request.form['specialization']
    cursor.execute("""
            UPDATE maintenance_personnel
            SET specialization = %s
            WHERE maintenance_personnel_id = %s
        """, (specialization,m_id,))
    mysql.connection.commit()
    cursor.close()

def getPersonnelClosedTickets(m_id=None):
    if m_id is None:
        m_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
            SELECT a.*,b.maintenance_personnel_id
            FROM ticket a
            JOIN ticket_personnel b ON a.ticket_id = b.ticket_id
            WHERE b.maintenance_personnel_id = %s AND a.status == 'closed'
            """, (m_id,))
    theTickets = cursor.fetchone()
    for ticket in theTickets:
        ticket['a.image_base64'] = citizen.get_image_base64(ticket['a.image_data'])

    return theTickets


def getCurrentPersonnell(m_id=None):
    if m_id is None:
        m_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT * FROM maintenance_personnel WHERE maintenance_personnel_id=%s
    """, (m_id,))
    result = cursor.fetchone()
    cursor.close()

    return result

def send_notification(ticket_id):
    cursor = mysql.connection.cursor()
    ticket = t_conditions.getTicket(ticket_id)
    reporter_id = citizen.getTicketReporterId(ticket)
    cursor.execute(
        """
        INSERT INTO notification
          (citizen_id, ticket_id, maintenance_personnel_id, notification_type, status, created_at, is_read)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s)
    """,
        (
            reporter_id,ticket_id,session['id'],'ticket closed',ticket['status'],datetime.now(),False
        )
    )
    mysql.connection.commit()



def updateTicketImage(ticket_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
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
    cursor.execute("""
            UPDATE ticket
            SET image_data = %s
            WHERE ticket_id = %s
        """, (camera_image_blob,ticket_id,))
    mysql.connection.commit()
