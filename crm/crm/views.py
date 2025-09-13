from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import timedelta
from .models import EmailAccount, Email, EmailFolder, EmailAttachment
from .forms import EmailAccountForm, EmailForm, QuickSetupForm, EmailSearchForm
import smtplib
import imaplib
import poplib
import email as email_module
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import ssl
from datetime import datetime, timedelta
import json
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

def landing(request):
    if request.method == 'POST':
        count = request.session.get('count', 0) + 1
        request.session['count'] = count
    else:
        count = request.session.get('count', 0)
    return render(request, 'landing.html', {'count': count})

def mailbox_home(request):
    """Enhanced mailbox home view with account management"""
    accounts = EmailAccount.objects.filter(is_active=True).order_by('-date_added')
    
    # Add email counts for each account
    for account in accounts:
        account.unread_count = account.get_unread_count()
        account.total_count = account.get_total_emails()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        accounts = accounts.filter(
            Q(name__icontains=search_query) | 
            Q(email_address__icontains=search_query)
        )
    
    context = {
        'accounts': accounts,
        'search_query': search_query,
        'total_accounts': EmailAccount.objects.filter(is_active=True).count(),
    }
    return render(request, 'mailbox/home.html', context)

def add_account(request):
    """Add a new email account"""
    # Initialize forms
    form = EmailAccountForm()
    quick_form = QuickSetupForm()
    
    if request.method == 'POST':
        if 'provider' in request.POST:
            # Quick setup form
            quick_form = QuickSetupForm(request.POST)
            if quick_form.is_valid():
                data = quick_form.cleaned_data
                account = create_account_from_provider(data)
                if account:
                    # Create default folders
                    create_default_folders(account)
                    messages.success(request, f'Account "{account.name}" added successfully with quick setup.')
                    return redirect('mailbox_home')
                else:
                    messages.error(request, 'Failed to create account with quick setup.')
        else:
            # Custom setup form
            form = EmailAccountForm(request.POST)
            if form.is_valid():
                account = form.save()
                # Create default folders
                create_default_folders(account)
                messages.success(request, f'Account "{account.name}" added successfully.')
                return redirect('mailbox_home')
            else:
                messages.error(request, 'Please correct the errors below.')
    
    context = {
        'form': form,
        'quick_form': quick_form,
    }
    return render(request, 'mailbox/add_account.html', context)

def create_account_from_provider(data):
    """Create email account from popular provider settings"""
    provider_settings = {
        'gmail': {
            'incoming_host': 'imap.gmail.com',
            'incoming_port': 993,
            'outgoing_host': 'smtp.gmail.com',
            'outgoing_port': 587,
            'protocol': 'IMAP',
        },
        'outlook': {
            'incoming_host': 'outlook.office365.com',
            'incoming_port': 993,
            'outgoing_host': 'smtp-mail.outlook.com',
            'outgoing_port': 587,
            'protocol': 'IMAP',
        },
        'yahoo': {
            'incoming_host': 'imap.mail.yahoo.com',
            'incoming_port': 993,
            'outgoing_host': 'smtp.mail.yahoo.com',
            'outgoing_port': 587,
            'protocol': 'IMAP',
        },
        'icloud': {
            'incoming_host': 'imap.mail.me.com',
            'incoming_port': 993,
            'outgoing_host': 'smtp.mail.me.com',
            'outgoing_port': 587,
            'protocol': 'IMAP',
        }
    }
    
    provider = data['provider']
    if provider in provider_settings:
        settings = provider_settings[provider]
        
        account = EmailAccount.objects.create(
            name=data['name'],
            email_address=data['email_address'],
            protocol=settings['protocol'],
            incoming_host=settings['incoming_host'],
            incoming_port=settings['incoming_port'],
            incoming_use_ssl=True,
            outgoing_host=settings['outgoing_host'],
            outgoing_port=settings['outgoing_port'],
            outgoing_use_ssl=True,
            username=data['email_address'],
            password=data['password'],
        )
        return account
    return None

def create_default_folders(account):
    """Create default folders for the account"""
    default_folders = [
        ('Inbox', 'inbox', True),
        ('Sent', 'sent', True),
        ('Drafts', 'drafts', True),
        ('Spam', 'spam', True),
        ('Trash', 'trash', True),
    ]
    
    for name, folder_type, is_system in default_folders:
        EmailFolder.objects.get_or_create(
            account=account,
            name=name,
            defaults={
                'folder_type': folder_type,
                'is_system': is_system
            }
        )

def view_emails(request, account_id):
    """Enhanced email view with folders, search, and pagination"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    # Get folder filter
    folder_id = request.GET.get('folder')
    selected_folder = None
    if folder_id:
        try:
            selected_folder = EmailFolder.objects.get(id=folder_id, account=account)
            emails = Email.objects.filter(account=account, folder=selected_folder)
        except EmailFolder.DoesNotExist:
            emails = Email.objects.filter(account=account)
    else:
        emails = Email.objects.filter(account=account)
    
    # Search functionality
    search_form = EmailSearchForm(request.GET)
    if search_form.is_valid():
        search_data = search_form.cleaned_data
        if search_data.get('query'):
            emails = emails.filter(
                Q(subject__icontains=search_data['query']) |
                Q(body__icontains=search_data['query']) |
                Q(sender__icontains=search_data['query'])
            )
        if search_data.get('sender'):
            emails = emails.filter(sender__icontains=search_data['sender'])
        if search_data.get('subject'):
            emails = emails.filter(subject__icontains=search_data['subject'])
        if search_data.get('date_from'):
            emails = emails.filter(email_date__gte=search_data['date_from'])
        if search_data.get('date_to'):
            emails = emails.filter(email_date__lte=search_data['date_to'])
    
    # Status filter
    status_filter = request.GET.get('status')
    if status_filter:
        emails = emails.filter(status=status_filter)
    
    # Read/Unread filter
    read_filter = request.GET.get('read')
    if read_filter == 'unread':
        emails = emails.filter(is_read=False)
    elif read_filter == 'read':
        emails = emails.filter(is_read=True)
    
    # Order emails
    emails = emails.order_by('-email_date')
    
    # Pagination
    paginator = Paginator(emails, 25)  # Show 25 emails per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get folders for sidebar
    folders = EmailFolder.objects.filter(account=account).order_by('folder_type', 'name')
    
    # Statistics
    stats = {
        'total': Email.objects.filter(account=account).count(),
        'unread': Email.objects.filter(account=account, is_read=False).count(),
        'sent': Email.objects.filter(account=account, status='sent').count(),
        'received': Email.objects.filter(account=account, status='received').count(),
    }
    
    context = {
        'account': account,
        'emails': page_obj,
        'folders': folders,
        'selected_folder': selected_folder,
        'search_form': search_form,
        'stats': stats,
        'status_choices': Email.STATUS_CHOICES,
        'status_filter': status_filter,
        'read_filter': read_filter,
    }
    return render(request, 'mailbox/emails.html', context)

def send_email(request, account_id):
    """Enhanced send email with CC, BCC, and better error handling"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    # Handle reply functionality
    reply_to_id = request.GET.get('reply_to')
    reply_to_email = None
    initial_data = {}
    
    if reply_to_id:
        try:
            reply_to_email = get_object_or_404(Email, id=reply_to_id, account=account)
            # Prepare initial data for reply
            initial_data = {
                'recipient': reply_to_email.sender,
                'subject': f"Re: {reply_to_email.subject}" if not reply_to_email.subject.startswith('Re:') else reply_to_email.subject,
                'body': f"\n\n--- Original Message ---\nFrom: {reply_to_email.sender}\nDate: {reply_to_email.email_date.strftime('%Y-%m-%d %H:%M:%S')}\nSubject: {reply_to_email.subject}\n\n{reply_to_email.body}",
            }
            # Add CC if there were other recipients in the original email
            original_recipients = reply_to_email.get_recipients_list()
            original_cc = reply_to_email.get_cc_list()
            
            # Include original sender and other recipients in CC (excluding current account)
            cc_list = []
            for recipient in original_recipients:
                if recipient.lower() != account.email_address.lower() and recipient.lower() != reply_to_email.sender.lower():
                    cc_list.append(recipient)
            cc_list.extend(original_cc)
            
            if cc_list:
                initial_data['cc'] = ', '.join(cc_list)
                
        except Email.DoesNotExist:
            messages.error(request, 'Original email not found.')
            return redirect('view_emails', account_id=account.id)
    
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            email_obj = form.save(commit=False)
            email_obj.account = account
            email_obj.sender = account.email_address
            email_obj.status = 'draft'  # Start as draft
            email_obj.email_date = timezone.now()
            
            # Set reply relationship if this is a reply
            if reply_to_email:
                email_obj.in_reply_to = reply_to_email.message_id
            
            # Send the email
            try:
                msg = MIMEMultipart()
                msg['From'] = account.email_address
                msg['To'] = email_obj.recipient
                msg['Subject'] = email_obj.subject
                
                # Add CC and BCC if provided
                if email_obj.cc:
                    msg['Cc'] = email_obj.cc
                
                # Attach body
                msg.attach(MIMEText(email_obj.body, 'plain'))
                
                # Connect to SMTP server
                if account.outgoing_use_ssl:
                    server = smtplib.SMTP_SSL(account.outgoing_host, account.outgoing_port)
                else:
                    server = smtplib.SMTP(account.outgoing_host, account.outgoing_port)
                    server.starttls()
                
                server.login(account.username, account.password)
                
                # Prepare recipient list
                recipients = email_obj.get_recipients_list()
                if email_obj.cc:
                    recipients.extend(email_obj.get_cc_list())
                if email_obj.bcc:
                    recipients.extend(email_obj.get_bcc_list())
                
                # Send email
                server.sendmail(account.email_address, recipients, msg.as_string())
                server.quit()
                
                # Update status and save
                email_obj.status = 'sent'
                
                # Assign to sent folder
                sent_folder, created = EmailFolder.objects.get_or_create(
                    account=account,
                    name='Sent',
                    defaults={'folder_type': 'sent', 'is_system': True}
                )
                email_obj.folder = sent_folder
                
                email_obj.save()
                
                # Update last sync time
                account.last_sync = timezone.now()
                account.save()
                
                messages.success(request, 'Email sent successfully!')
                return redirect('view_emails', account_id=account.id)
                
            except smtplib.SMTPAuthenticationError:
                email_obj.status = 'failed'
                email_obj.save()
                messages.error(request, 'Authentication failed. Please check your email credentials.')
            except smtplib.SMTPRecipientsRefused:
                email_obj.status = 'failed'
                email_obj.save()
                messages.error(request, 'One or more recipients were refused by the server.')
            except smtplib.SMTPException as e:
                email_obj.status = 'failed'
                email_obj.save()
                messages.error(request, f'SMTP error occurred: {str(e)}')
            except Exception as e:
                email_obj.status = 'failed'
                email_obj.save()
                messages.error(request, f'Failed to send email: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        # Initialize form with reply data if available
        form = EmailForm(initial=initial_data)
    
    context = {
        'form': form,
        'account': account,
        'reply_to_email': reply_to_email,
    }
    return render(request, 'mailbox/send_email.html', context)

def fetch_emails(request, account_id):
    """Enhanced email fetching with IMAP, POP3 support and better parsing"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    try:
        if account.protocol == 'IMAP':
            email_count = fetch_emails_imap(account)
        elif account.protocol == 'POP3':
            email_count = fetch_emails_pop3(account)
        else:
            messages.error(request, f'Protocol {account.protocol} not supported for fetching emails.')
            return redirect('view_emails', account_id=account.id)
            
        # Update last sync time
        account.last_sync = timezone.now()
        account.save()
        
        account_date = account.date_added.strftime('%B %d, %Y')
        messages.success(request, f'Successfully synced {email_count} emails from {account_date} onwards!')
        
    except Exception as e:
        messages.error(request, f'Failed to fetch emails: {str(e)}')
    
    return redirect('view_emails', account_id=account.id)

def fetch_emails_imap(account):
    """Fetch emails using IMAP protocol"""
    # Connect to IMAP server
    if account.incoming_use_ssl:
        mail = imaplib.IMAP4_SSL(account.incoming_host, account.incoming_port)
    else:
        mail = imaplib.IMAP4(account.incoming_host, account.incoming_port)
    
    mail.login(account.username, account.password)
    mail.select('inbox')
    
    # Search for emails since account was added
    sync_date = account.date_added.strftime('%d-%b-%Y')
    status, messages_list = mail.search(None, f'SINCE {sync_date}')
    
    if status == 'OK':
        # Get inbox folder
        inbox_folder, created = EmailFolder.objects.get_or_create(
            account=account,
            name='Inbox',
            defaults={'folder_type': 'inbox', 'is_system': True}
        )
        
        email_count = 0
        for num in messages_list[0].split():
            try:
                status, data = mail.fetch(num, '(RFC822)')
                if status == 'OK':
                    raw_email = data[0][1]
                    email_message = email_module.message_from_bytes(raw_email)
                    
                    # Parse email details
                    email_details = parse_email_message(email_message, account)
                    
                    # Check if email already exists
                    if not Email.objects.filter(
                        account=account, 
                        message_id=email_details.get('message_id', '')
                    ).exists():
                        
                        Email.objects.create(
                            account=account,
                            folder=inbox_folder,
                            message_id=email_details.get('message_id', ''),
                            sender=email_details['sender'],
                            recipient=account.email_address,
                            cc=email_details.get('cc', ''),
                            subject=email_details['subject'],
                            body=email_details['body'],
                            html_body=email_details.get('html_body', ''),
                            email_date=email_details['date'],
                            status='received',
                            has_attachments=email_details.get('has_attachments', False)
                        )
                        email_count += 1
                        
            except Exception as e:
                print(f"Error processing email: {e}")
                continue
    
    mail.logout()
    return email_count

def fetch_emails_pop3(account):
    """Fetch emails using POP3 protocol"""
    # Connect to POP3 server
    if account.incoming_use_ssl:
        mail = poplib.POP3_SSL(account.incoming_host, account.incoming_port)
    else:
        mail = poplib.POP3(account.incoming_host, account.incoming_port)
    
    mail.user(account.username)
    mail.pass_(account.password)
    
    # Get inbox folder
    inbox_folder, created = EmailFolder.objects.get_or_create(
        account=account,
        name='Inbox',
        defaults={'folder_type': 'inbox', 'is_system': True}
    )
    
    # Get number of messages
    num_messages = len(mail.list()[1])
    email_count = 0
    
    # Fetch recent emails (last 50 to avoid overwhelming)
    start_index = max(1, num_messages - 50)
    
    for i in range(start_index, num_messages + 1):
        try:
            # Get email
            raw_email = b'\n'.join(mail.retr(i)[1])
            email_message = email_module.message_from_bytes(raw_email)
            
            # Parse email details
            email_details = parse_email_message(email_message, account)
            
            # Only process emails from account creation date onwards
            if email_details['date'] >= account.date_added:
                # Check if email already exists
                if not Email.objects.filter(
                    account=account,
                    message_id=email_details.get('message_id', ''),
                    sender=email_details['sender'],
                    email_date=email_details['date']
                ).exists():
                    
                    Email.objects.create(
                        account=account,
                        folder=inbox_folder,
                        message_id=email_details.get('message_id', ''),
                        sender=email_details['sender'],
                        recipient=account.email_address,
                        cc=email_details.get('cc', ''),
                        subject=email_details['subject'],
                        body=email_details['body'],
                        html_body=email_details.get('html_body', ''),
                        email_date=email_details['date'],
                        status='received',
                        has_attachments=email_details.get('has_attachments', False)
                    )
                    email_count += 1
                
        except Exception as e:
            print(f"Error processing email: {e}")
            continue
    
    mail.quit()
    return email_count

def parse_email_message(email_message, account):
    """Parse email message and extract details"""
    # Get sender
    sender = email_message.get('From', 'unknown@example.com')
    if sender:
        sender = decode_email_header(sender)
    
    # Get subject
    subject = email_message.get('Subject', '')
    if subject:
        subject = decode_email_header(subject)
    
    # Get date
    date_str = email_message.get('Date')
    try:
        if date_str:
            email_date = email_module.utils.parsedate_to_datetime(date_str)
        else:
            email_date = timezone.now()
    except:
        email_date = timezone.now()
    
    # Get message ID
    message_id = email_message.get('Message-ID', '')
    
    # Get CC
    cc = email_message.get('Cc', '')
    if cc:
        cc = decode_email_header(cc)
    
    # Get body
    body = ''
    html_body = ''
    has_attachments = False
    
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))
            
            # Skip attachments for now (can be enhanced later)
            if 'attachment' in content_disposition:
                has_attachments = True
                continue
                
            if content_type == 'text/plain' and not body:
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    body = str(part.get_payload())
                    
            elif content_type == 'text/html' and not html_body:
                try:
                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    html_body = str(part.get_payload())
    else:
        try:
            content = email_message.get_payload(decode=True)
            if content:
                body = content.decode('utf-8', errors='ignore')
            else:
                body = str(email_message.get_payload())
        except:
            body = str(email_message.get_payload())
    
    return {
        'sender': sender,
        'subject': subject,
        'body': body,
        'html_body': html_body,
        'date': email_date,
        'message_id': message_id,
        'cc': cc,
        'has_attachments': has_attachments,
    }

def decode_email_header(header):
    """Decode email header that might be encoded"""
    if not header:
        return ''
    
    try:
        decoded_header = decode_header(header)
        decoded_string = ''
        for part, encoding in decoded_header:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding, errors='ignore')
                else:
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += str(part)
        return decoded_string
    except:
        return str(header)

# Additional utility views

def mark_email_read(request, account_id, email_id):
    """Mark email as read/unread"""
    account = get_object_or_404(EmailAccount, id=account_id)
    email_obj = get_object_or_404(Email, id=email_id, account=account)
    
    if request.method == 'POST':
        email_obj.is_read = not email_obj.is_read
        email_obj.save()
        
        status = 'read' if email_obj.is_read else 'unread'
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Email marked as {status}.',
                'is_read': email_obj.is_read
            })
        
        messages.success(request, f'Email marked as {status}.')
    
    return redirect('view_emails', account_id=account.id)

def delete_email(request, account_id, email_id):
    """Delete or move email to trash"""
    account = get_object_or_404(EmailAccount, id=account_id)
    email_obj = get_object_or_404(Email, id=email_id, account=account)
    
    if request.method == 'POST':
        # Get or create trash folder
        trash_folder, created = EmailFolder.objects.get_or_create(
            account=account,
            name='Trash',
            defaults={'folder_type': 'trash', 'is_system': True}
        )
        
        # Move to trash instead of deleting
        email_obj.folder = trash_folder
        email_obj.save()
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Email moved to trash.'
            })
        
        messages.success(request, 'Email moved to trash.')
        
        # If accessed from email detail page, redirect to email list
        referer = request.META.get('HTTP_REFERER', '')
        if 'email' in referer and str(email_id) in referer:
            return redirect('view_emails', account_id=account.id)
    
    return redirect('view_emails', account_id=account.id)

def star_email(request, account_id, email_id):
    """Star/unstar email"""
    account = get_object_or_404(EmailAccount, id=account_id)
    email_obj = get_object_or_404(Email, id=email_id, account=account)
    
    if request.method == 'POST':
        email_obj.is_starred = not email_obj.is_starred
        email_obj.save()
        
        status = 'starred' if email_obj.is_starred else 'unstarred'
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Email {status}.',
                'is_starred': email_obj.is_starred
            })
        
        messages.success(request, f'Email {status}.')
    
    return redirect('view_emails', account_id=account.id)

def email_detail(request, account_id, email_id):
    """View email details"""
    account = get_object_or_404(EmailAccount, id=account_id)
    email_obj = get_object_or_404(Email, id=email_id, account=account)
    
    # Mark as read when viewing
    if not email_obj.is_read:
        email_obj.is_read = True
        email_obj.save()
    
    context = {
        'account': account,
        'email': email_obj,
    }
    return render(request, 'mailbox/email_detail.html', context)

def toggle_account_status(request, account_id):
    """Activate/deactivate email account"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    if request.method == 'POST':
        account.is_active = not account.is_active
        account.save()
        
        status = 'activated' if account.is_active else 'deactivated'
        messages.success(request, f'Account {status}.')
    
    return redirect('mailbox_home')

def account_settings(request, account_id):
    """Edit account settings"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    if request.method == 'POST':
        form = EmailAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account settings updated successfully.')
            return redirect('mailbox_home')
    else:
        form = EmailAccountForm(instance=account)
    
    context = {
        'form': form,
        'account': account,
        'editing': True,
    }
    return render(request, 'mailbox/add_account.html', context)

@require_POST
def bulk_mark_read(request, account_id):
    """Mark multiple emails as read"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    try:
        data = json.loads(request.body)
        email_ids = data.get('email_ids', [])
        
        updated_count = Email.objects.filter(
            account=account,
            id__in=email_ids
        ).update(is_read=True)
        
        return JsonResponse({
            'success': True,
            'message': f'Marked {updated_count} emails as read'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_POST
def bulk_mark_unread(request, account_id):
    """Mark multiple emails as unread"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    try:
        data = json.loads(request.body)
        email_ids = data.get('email_ids', [])
        
        updated_count = Email.objects.filter(
            account=account,
            id__in=email_ids
        ).update(is_read=False)
        
        return JsonResponse({
            'success': True,
            'message': f'Marked {updated_count} emails as unread'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_POST
def bulk_delete(request, account_id):
    """Move multiple emails to trash"""
    account = get_object_or_404(EmailAccount, id=account_id)
    
    try:
        data = json.loads(request.body)
        email_ids = data.get('email_ids', [])
        
        # Get or create trash folder
        trash_folder, created = EmailFolder.objects.get_or_create(
            account=account,
            name='Trash',
            defaults={'folder_type': 'trash', 'is_system': True}
        )
        
        # Move emails to trash instead of deleting
        updated_count = Email.objects.filter(
            account=account,
            id__in=email_ids
        ).update(folder=trash_folder)
        
        return JsonResponse({
            'success': True,
            'message': f'Moved {updated_count} emails to trash'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
