import json
import re
import requests
import frappe
from frappe import enqueue
import google.auth.transport.requests
from google.oauth2 import service_account

frappe.utils.logger.set_log_level("DEBUG")
logger = frappe.logger("fcm_erpnext", allow_site=True, max_size=10000000, file_count=20)

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
    logger.info(f"Sending to {device_id.device_id}")
    message = notification.email_content
    title = notification.subject
    if message:
        message = convert_message(message)
    if title:
        title = convert_message(title)

    
    url = f"https://fcm.googleapis.com/v1/projects/{info.project_id}/messages:send"

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
    logger.info(f"Post status {req.text}")
    frappe.log_error(req.text)
