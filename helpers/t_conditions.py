import MySQLdb.cursors
from app import mysql



def estimatedDuration(incidentType):
    if incidentType == "Pothole":
        return 320
    elif incidentType == "Street Light":
        return 120
    elif incidentType == "Garbage Collection":
        return 90
    elif incidentType == "Broken Sidewalk":
        return 240
    else:
        return 400


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

def inTime(iDuration,estimatedDuration):
    if iDuration>estimatedDuration:
        return "time exceeded"
    else:
        return "within estimated time"

def getSpecialization(ticket_type):
    if ticket_type == "Pothole":
        return 'civil'
    elif ticket_type == "Street Light":
        return 'electrical'
    elif ticket_type == "Garbage Collection":
        return 'sanitation'
    elif ticket_type == "Broken Sidewalk":
        return 'civil'
    else:
        return 'general'

def getTicket(ticket_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM ticket WHERE ticket_id = %s", (ticket_id,))
    ticket = cursor.fetchone()
    return ticket

def countTicketPersonnel(ticket_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT count(maintenance_personnel_id) as counted FROM ticket_personnel WHERE ticket_id = %s", (ticket_id,))
    count = cursor.fetchone()
    return count

def getPersonnelClosedTickets(m_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
            SELECT a.*,b.maintenance_personnel_id
            FROM ticket a
            JOIN ticket_personnel b ON a.ticket_id = b.ticket_id
            WHERE b.maintenance_personnel_id = %s AND a.status = 'closed'
            """, (m_id,))
    ticket =cursor.fetchall()
    return ticket

