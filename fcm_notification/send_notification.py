import json
import re
import requests
import frappe
from frappe import enqueue
import google.auth.transport.requests
from google.oauth2 import service_account


def user_id(doc):
    user_email = doc.for_user
    user_device_id = frappe.get_all(
        "User Device", filters={"user": user_email}, fields=["device_id"]
    )
    return user_device_id


@frappe.whitelist()
def send_notification(doc, event):
    device_ids = user_id(doc)
    for device_id in device_ids:
        enqueue(
            process_notification,
            queue="default",
            now=False,
            device_id=device_id,
            notification=doc,
        )


def convert_message(message):
    CLEANR = re.compile("<.*?>")
    cleanmessage = re.sub(CLEANR, "", message)
    # cleantitle = re.sub(CLEANR, "",title)
    return cleanmessage


def _get_access_token(info):
  """Retrieve a valid access token that can be used to authorize requests.

  :return: Access token.
  """
  credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
  #credentials = service_account.Credentials.from_service_account_file(
  #  'service-account.json', scopes=SCOPES)
  request = google.auth.transport.requests.Request()
  credentials.refresh(request)
  return credentials.token


def process_notification(device_id, notification):
    info = frappe.db.get_single_value("FCM Notification Settings", "service_account_info")
    message = notification.email_content
    title = notification.subject
    if message:
        message = convert_message(message)
    if title:
        title = convert_message(title)

    
    url = "https://fcm.googleapis.com/v1/projects/{}/messages:send".format(info.project_id)

    body = {
        "message": {
            "token": device_id.device_id,
            "notification": {"body": message, "title": title},
            "data": {
                "doctype": notification.document_type,
                "docname": notification.document_name,
            }
        }
    }

    req = requests.post(
        url=url,
        data=json.dumps(body),
        headers = {
            'Authorization': 'Bearer ' + _get_access_token(),
            'Content-Type': 'application/json; UTF-8',
        },
    )
    frappe.log_error(req.text)


def process_notification_legacy(device_id, notification):
    message = notification.email_content
    title = notification.subject
    if message:
        message = convert_message(message)
    if title:
        title = convert_message(title)

    url = "https://fcm.googleapis.com/fcm/send"
    body = {
        "to": device_id.device_id,
        "notification": {"body": message, "title": title},
        "data": {
            "doctype": notification.document_type,
            "docname": notification.document_name,
        },
    }

    server_key = frappe.db.get_single_value("FCM Notification Settings", "server_key")
    auth = f"Bearer {server_key}"
    req = requests.post(
        url=url,
        data=json.dumps(body),
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    frappe.log_error(req.text)
