from django.core.mail.backends.base import BaseEmailBackend
import boto3
from botocore.exceptions import ClientError
from decouple import config
import logging
import email

logger = logging.getLogger(__name__)

class SESEmailBackend(BaseEmailBackend):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.debug("Initializing SESEmailBackend...")
        self.client = None

    def open(self):
        logger.debug("Opening SES client connection...")
        if self.client is None:
            try:
                self.client = boto3.client(
                    'ses',
                    region_name=config('AWS_SES_REGION', default='eu-west-2'),
                    aws_access_key_id=config('AWS_SES_ACCESS_KEY_ID'),
                    aws_secret_access_key=config('AWS_SES_SECRET_ACCESS_KEY')
                )
                logger.debug("SES client opened.")
                return True
            except Exception as e:
                logger.error("Failed to open SES client: %s", str(e))
                return False
        return True

    def close(self):
        logger.debug("Closing SES client connection...")
        self.client = None
        logger.debug("SES client closed.")

    def send_messages(self, email_messages):
        logger.debug("Processing %d email messages...", len(email_messages))
        if not self.open():
            logger.error("Cannot send messages: SES client not initialized.")
            raise ValueError("SES client not initialized.")

        sent_count = 0
        for message in email_messages:
            try:
                logger.debug("Preprocessing email: subject=%s, to=%s", message.subject, message.to)
                # Convert EmailMessage to raw MIME for SES raw sending
                raw_message = message.message().as_string()
                destinations = {'ToAddresses': message.to}
                if getattr(message, 'cc', None):
                    destinations['CcAddresses'] = message.cc
                    logger.debug("CC: %s", message.cc)
                if getattr(message, 'bcc', None):
                    destinations['BccAddresses'] = message.bcc
                    logger.debug("BCC: %s", message.bcc)

                logger.debug("Sending SES API raw request...")
                response = self.client.send_raw_email(
                    Source=message.from_email,
                    Destinations=message.to + (message.cc or []) + (message.bcc or []),
                    RawMessage={'Data': raw_message}
                )
                logger.debug("Email sent, Message ID: %s", response['MessageId'])
                sent_count += 1
            except ClientError as e:
                logger.error("SES API error: %s", e.response['Error']['Message'])
                print(f"Error sending email: {e.response['Error']['Message']}")
                if not self.fail_silently:
                    raise e
            except Exception as e:
                logger.error("Unexpected error: %s", str(e))
                print(f"Unexpected error: {str(e)}")
                if not self.fail_silently:
                    raise e
        logger.debug("Sent %d emails successfully.", sent_count)
        return sent_count
