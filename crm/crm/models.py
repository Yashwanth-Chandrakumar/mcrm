from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class EmailAccount(models.Model):
    PROTOCOL_CHOICES = [
        ('IMAP', 'IMAP'),
        ('POP3', 'POP3'),
        ('SMTP', 'SMTP'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100, default="Untitled Account", help_text="Display name for this account")
    email_address = models.EmailField(default="example@email.com", help_text="Email address")
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, default='IMAP')
    
    # Incoming mail settings
    incoming_host = models.CharField(max_length=100, default="imap.gmail.com", help_text="IMAP/POP3 server host")
    incoming_port = models.IntegerField(default=993, help_text="IMAP/POP3 server port")
    incoming_use_ssl = models.BooleanField(default=True, help_text="Use SSL for incoming mail")
    
    # Outgoing mail settings (SMTP)
    outgoing_host = models.CharField(max_length=100, default="smtp.gmail.com", help_text="SMTP server host")
    outgoing_port = models.IntegerField(default=587, help_text="SMTP server port")
    outgoing_use_ssl = models.BooleanField(default=True, help_text="Use SSL for outgoing mail")
    
    username = models.CharField(max_length=100, default="username")
    password = models.CharField(max_length=100, default="password")  # Use encrypted in production
    
    is_active = models.BooleanField(default=True)
    date_added = models.DateTimeField(default=timezone.now)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    # Email sync settings
    sync_from_date = models.DateTimeField(default=timezone.now, help_text="Start syncing emails from this date")
    auto_sync = models.BooleanField(default=True, help_text="Automatically sync emails")
    
    class Meta:
        ordering = ['-date_added']
        # unique_together = ['user', 'email_address']  # Will add this back in a separate migration

    def __str__(self):
        return f"{self.name} ({self.email_address})"
    
    def get_unread_count(self):
        return self.emails.filter(status='received', is_read=False).count()
    
    def get_total_emails(self):
        return self.emails.count()

class EmailFolder(models.Model):
    FOLDER_TYPES = [
        ('inbox', 'Inbox'),
        ('sent', 'Sent'),
        ('drafts', 'Drafts'),
        ('spam', 'Spam'),
        ('trash', 'Trash'),
        ('custom', 'Custom'),
    ]
    
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=100, default="Inbox")
    folder_type = models.CharField(max_length=20, choices=FOLDER_TYPES, default='custom')
    is_system = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
        unique_together = ['account', 'name']
    
    def __str__(self):
        return f"{self.account.name} - {self.name}"

class Email(models.Model):
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('sent', 'Sent'),
        ('draft', 'Draft'),
        ('failed', 'Failed'),
    ]
    
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='emails')
    folder = models.ForeignKey(EmailFolder, on_delete=models.CASCADE, null=True, blank=True)
    
    message_id = models.CharField(max_length=255, null=True, blank=True, default="", help_text="Unique message ID from email server")
    sender = models.EmailField(default="sender@example.com")
    recipient = models.TextField(default="recipient@example.com", help_text="Comma-separated list of recipients")
    cc = models.TextField(blank=True, default="", help_text="CC recipients")
    bcc = models.TextField(blank=True, default="", help_text="BCC recipients")
    
    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")
    html_body = models.TextField(blank=True, default="", help_text="HTML version of email body")
    
    timestamp = models.DateTimeField(default=timezone.now)
    email_date = models.DateTimeField(default=timezone.now, help_text="Original email date from headers")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='received')
    
    is_read = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    
    # Attachments
    has_attachments = models.BooleanField(default=False)
    
    # Threading
    thread_id = models.CharField(max_length=255, null=True, blank=True, default="")
    in_reply_to = models.CharField(max_length=255, null=True, blank=True, default="")
    
    class Meta:
        ordering = ['-email_date']
        # unique_together = ['account', 'message_id']  # Will add this back in a separate migration

    def __str__(self):
        return f"{self.subject} - {self.sender}"
    
    def get_recipients_list(self):
        return [email.strip() for email in self.recipient.split(',') if email.strip()]
    
    def get_cc_list(self):
        return [email.strip() for email in self.cc.split(',') if email.strip()] if self.cc else []
    
    def get_bcc_list(self):
        return [email.strip() for email in self.bcc.split(',') if email.strip()] if self.bcc else []

class EmailAttachment(models.Model):
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name='attachments')
    filename = models.CharField(max_length=255, default="attachment.txt")
    content_type = models.CharField(max_length=100, default="text/plain")
    size = models.IntegerField(default=0, help_text="Size in bytes")
    file_data = models.BinaryField(default=b'')  # Store small attachments directly
    
    def __str__(self):
        return f"{self.filename} ({self.email.subject})"
