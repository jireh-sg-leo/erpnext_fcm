import json
import re
import requests
import frappe
from frappe import enqueue
import google.auth.transport.requests
from google.oauth2 import service_account

frappe.utils.logger.set_log_level("DEBUG")
logger = frappe.logger("fcm_erpnext", allow_site=True, max_size=10000000, file_count=20)

SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']

def user_id(doc):
    user_email = doc.for_user
    user_device_id = frappe.get_all(
        "User Device", filters={"user": user_email, "enabled": 1}, fields=["name", "device_id"]
    )
    return user_device_id


@frappe.whitelist()
def send_notification(doc, event):
    device_ids = user_id(doc)
    logger.info(device_ids)
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
  request = google.auth.transport.requests.Request()
  credentials.refresh(request)
  return credentials.token


def process_notification(device_id, notification):
    info = frappe.db.get_single_value("FCM Notification Settings", "service_account_info")
    config = json.loads(info)
    logger.info(f"Sending to {device_id.device_id}")
    message = notification.email_content
    title = notification.subject
    if message:
        message = convert_message(message)
    if title:
        title = convert_message(title)

    
    url = f"https://fcm.googleapis.com/v1/projects/{config['project_id']}/messages:send"

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
            'Authorization': 'Bearer ' + _get_access_token(config),
            'Content-Type': 'application/json; UTF-8',
        },
    )
    res_json = json.loads(req.text)
    if res_json['error']:
        err = res_json['error']
        if (err['code'] == 404):
            # Disable device if not found
            logger.info(f"Disabling {device_id.device_id} {device_id.name}")
            frappe.db.set_value('User Device', device_id.name, 'enabled', 0)
        logger.warning(f"{err['message']}")
        return
    logger.info(f"FCM {res_json['name']}")
