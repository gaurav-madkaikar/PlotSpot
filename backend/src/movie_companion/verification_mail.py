"""Explicit local preview or TLS SMTP. No email addresses or links are logged."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit

from email_validator import EmailNotValidError, validate_email


class MailUnavailable(RuntimeError):
    pass


def normalized_email(value):
    try:
        address = validate_email(value, check_deliverability=False, allow_smtputf8=False)
        return address.ascii_email
    except EmailNotValidError:
        raise ValueError('Enter a valid email address.') from None


class VerificationMail:
    def __init__(self, *, mode='disabled', origin='http://127.0.0.1:5173',
                 host='', port=587, username='', password='', sender='', tls='starttls'):
        self.mode = mode
        self.origin = origin
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender
        self.tls = tls
        parts = urlsplit(origin)
        if mode not in ('disabled', 'preview', 'smtp'):
            raise ValueError('PLOTSPOT_VERIFICATION_MODE must be disabled, preview or smtp.')
        if mode == 'preview' and (parts.scheme != 'http' or parts.hostname not in ('127.0.0.1', 'localhost', '::1')):
            raise ValueError('Verification preview is restricted to loopback HTTP development.')
        if mode == 'smtp':
            if not host or not 1 <= port <= 65535 or tls not in ('starttls', 'ssl') or bool(username) != bool(password):
                raise ValueError('Configure an SMTP host, port, TLS mode and matching credentials.')
            self.sender = normalized_email(sender)

    @classmethod
    def configured(cls, origin):
        return cls(mode=os.getenv('PLOTSPOT_VERIFICATION_MODE', 'disabled'), origin=origin,
                   host=os.getenv('PLOTSPOT_SMTP_HOST', ''), port=int(os.getenv('PLOTSPOT_SMTP_PORT', '587')),
                   username=os.getenv('PLOTSPOT_SMTP_USERNAME', ''), password=os.getenv('PLOTSPOT_SMTP_PASSWORD', ''),
                   sender=os.getenv('PLOTSPOT_SMTP_FROM', ''), tls=os.getenv('PLOTSPOT_SMTP_TLS', 'starttls'))

    def require_available(self):
        if self.mode == 'disabled':
            raise MailUnavailable('Email verification is not configured. Please try again later.')

    def deliver(self, recipient, username, path):
        self.require_available()
        if self.mode == 'preview':
            return path
        message = EmailMessage()
        message['From'] = self.sender
        message['To'] = recipient
        message['Subject'] = 'Verify your PlotSpot email'
        message.set_content(f'Welcome to PlotSpot, {username}.\n\n'
                            f'If you created this account, confirm your email here:\n{self.origin}{path}\n\n'
                            'This link expires in 30 minutes and works once. '
                            'If you did not request it, ignore this email.\n')
        try:
            context = ssl.create_default_context()
            client = (smtplib.SMTP_SSL(self.host, self.port, timeout=10, context=context)
                      if self.tls == 'ssl' else smtplib.SMTP(self.host, self.port, timeout=10))
            with client:
                if self.tls == 'starttls':
                    client.ehlo()
                    client.starttls(context=context)
                    client.ehlo()
                if self.username:
                    client.login(self.username, self.password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException):
            raise MailUnavailable('Verification email could not be sent. Please try again shortly.') from None
        return None
