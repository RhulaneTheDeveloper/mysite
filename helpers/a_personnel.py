import MySQLdb.cursors
from . import m_personnel, t_conditions, citizen
import base64
from flask import Flask, render_template, request, url_for, session, redirect, flash,jsonify
from app import mysql


def getPersonnelTicket(p_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
SELECT * FROM ticket
WHERE ticket_id IN (
    SELECT ticket_id FROM ticket_personnel WHERE maintenance_personnel_id = %s
)
""", (p_id,))

    theTickets = cursor.fetchall()
    for ticket in theTickets:
        if ticket['image_data']:
            encoded = base64.b64encode(ticket['image_data']).decode('utf-8')
            ticket['image_base64'] = citizen.get_image_base64(ticket['image_data'])

    return theTickets
