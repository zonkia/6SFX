from __future__ import print_function
import httplib2
import os
import pandas as pd

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import base64
from email.mime.text import MIMEText
from email.mime.audio import MIMEAudio
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import mimetypes

os.chdir(os.path.dirname(__file__))

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/gmail-python-quickstart.json
SCOPES = 'https://mail.google.com/'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'GmailAPI'


class send_email:
    def __init__(self, service):
        self.service = service

    def create_message(self, sender, to, subject, message_text):
        message = MIMEText(message_text)
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes())
        raw = raw.decode()
        return {'raw': raw}

    def create_html_message(self, sender, to, subject, dataFrames=None, file=None):
        message = MIMEMultipart()
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject

        for dataFrame in dataFrames:
            html = """\
            <html>
            <head></head>
            <body>
                {0}
                <br>
            </body>
            </html>
            """.format(dataFrame.to_html())
            part1 = MIMEText(html, 'html')
            message.attach(part1)

        raw = base64.urlsafe_b64encode(message.as_bytes())
        raw = raw.decode()
        return {'raw': raw}

    def create_message_with_attachment(self, sender, to, subject, msgPlain,   attachmentFile=None, dataFrames=None):
        message = MIMEMultipart('mixed')
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject

        for dataFrame in dataFrames:
            if str(type(dataFrame)) != "<class 'pandas.core.frame.DataFrame'>":
                pass
            else:
                html = """\
                <html>
                <head></head>
                <body>
                    {0}
                    <br>
                </body>
                </html>
                """.format(dataFrame.to_html())

                part1 = MIMEText(html, 'html')
                message.attach(part1)

        messageA = MIMEText(msgPlain)
        message.attach(messageA)

        if attachmentFile:
            for attatchment in attachmentFile:
                content_type, encoding = mimetypes.guess_type(attatchment)
                if content_type is None or encoding is not None:
                    content_type = 'application/octet-stream'
                main_type, sub_type = content_type.split('/', 1)
                if main_type == 'text':
                    fp = open(attatchment, 'rb')
                    msg = MIMEText(fp.read(), _subtype=sub_type)
                    fp.close()
                elif main_type == 'image':
                    fp = open(attatchment, 'rb')
                    msg = MIMEImage(fp.read(), _subtype=sub_type)
                    fp.close()
                elif main_type == 'audio':
                    fp = open(attatchment, 'rb')
                    msg = MIMEAudio(fp.read(), _subtype=sub_type)
                    fp.close()
                else:
                    fp = open(attatchment, 'rb')
                    msg = MIMEBase(main_type, sub_type)
                    msg.set_payload(fp.read())
                    fp.close()
                filename = os.path.basename(attatchment)
                msg.add_header('Content-Disposition',
                               'attachment', filename=filename)
                message.attach(msg)
        raw = base64.urlsafe_b64encode(message.as_bytes())
        raw = raw.decode()
        return {'raw': raw}

    def send_message(self, user_id, message):
        message = (self.service.users().messages().send(
            userId=user_id, body=message).execute())
        print('Message Id: %s' % message['id'])
        return message

    def create_message(self, sender, to, subject, message_text):
        message = MIMEText(message_text)
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes())
        raw = raw.decode()
        return {'raw': raw}


def get_credentials():
    home_dir = os.path.dirname(__file__)
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'gmail-python.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials


class SendMessage():

    def __init__(self, receiver, subject, body, file=None, dataFrames=None):
        try:
            credentials = get_credentials()
            http = credentials.authorize(httplib2.Http())
            service = discovery.build(
                'gmail', 'v1', http=http, cache_discovery=False)

            sendInst = send_email(service)

            message = sendInst.create_message_with_attachment(
                "pythonautotrader@gmail.com", receiver, subject, body, file, dataFrames)

            sendInst.send_message('me', message)
        except:
            pass
