import os
import json
import csv
import smtplib
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import pandas as pd

# === Configuration ===
DEBUG = True  # Set to True to send only one email to yashwanthsc1@gmail.com
DAILY_EMAIL_LIMIT = 100
CLIENT_EMAIL_LIMIT = 100  # Maximum emails per client
CONFIG_FILE = 'config.json'
MAILDATA_FILE = 'maildata.xlsx'

# Thread-safe lock for file operations
file_lock = threading.Lock()

def load_config():
    """Load configuration from config.json"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"❌ Configuration file '{CONFIG_FILE}' not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing '{CONFIG_FILE}': {e}")
        return []

def load_template(template_file):
    """Load email templates from JSON file"""
    template_path = os.path.join('templates', template_file)
    try:
        with open(template_path, 'r') as f:
            templates = json.load(f)
        return templates
    except FileNotFoundError:
        print(f"❌ Template file '{template_path}' not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing template file '{template_path}': {e}")
        return []

def get_sent_emails(client_name):
    """Get list of already sent email addresses for a client"""
    sent_file = os.path.join('sentdata', f"{client_name}.csv")
    sent_emails = set()
    
    if os.path.exists(sent_file):
        try:
            with open(sent_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header if exists
                for row in reader:
                    if row:  # Skip empty rows
                        sent_emails.add(row[0].strip().lower())
        except Exception as e:
            print(f"⚠️ Error reading sent emails file '{sent_file}': {e}")
    
    return sent_emails

def save_sent_email(client_name, email, timestamp):
    """Save sent email to CSV file (thread-safe)"""
    sent_file = os.path.join('sentdata', f"{client_name}.csv")
    
    # Use thread-safe lock for file operations
    with file_lock:
        # Create sentdata directory if it doesn't exist
        os.makedirs('sentdata', exist_ok=True)
        
        # Check if file exists to determine if we need to write header
        file_exists = os.path.exists(sent_file)
        
        try:
            with open(sent_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['Email', 'Timestamp'])  # Header
                writer.writerow([email, timestamp])
        except Exception as e:
            print(f"❌ Error saving sent email to '{sent_file}': {e}")

def load_mail_data():
    """Load email data from Excel file"""
    try:
        df = pd.read_excel(MAILDATA_FILE)
        # Clean the data
        df.dropna(how='all', inplace=True)
        df.dropna(subset=['Email'], how='any', inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
    except FileNotFoundError:
        print(f"❌ Mail data file '{MAILDATA_FILE}' not found.")
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ Error loading mail data: {e}")
        return pd.DataFrame()

def get_attachments(attachments_folder):
    """Get all files from the attachments folder"""
    attachments_path = os.path.join('attachments', attachments_folder)
    attachment_files = []
    
    if os.path.exists(attachments_path):
        for file in os.listdir(attachments_path):
            file_path = os.path.join(attachments_path, file)
            if os.path.isfile(file_path):
                attachment_files.append(file_path)
    else:
        print(f"⚠️ Attachments folder '{attachments_path}' not found.")
    
    return attachment_files

def create_message(config, template, recipient_data, attachments):
    """Create email message with random template selection"""
    # Randomly select a template if multiple exist
    selected_template = random.choice(template)
    
    msg = MIMEMultipart('alternative')
    msg['From'] = config['email_account']
    msg['To'] = recipient_data['Email']
    msg['Subject'] = selected_template['subject']
    
    # Format the body with recipient data
    html_body = '\n'.join(selected_template['body'])
    
    # Replace placeholders with actual data
    for column in recipient_data.index:
        placeholder = f"{{{column.lower().replace(' ', '_')}}}"
        if placeholder in html_body:
            html_body = html_body.replace(placeholder, str(recipient_data[column]))
    
    # Add HTML content
    msg.attach(MIMEText(html_body, 'html'))
    
    # Attach files
    for attachment_path in attachments:
        try:
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{os.path.basename(attachment_path)}"'
                )
                msg.attach(part)
        except Exception as e:
            print(f"⚠️ Failed to attach file '{attachment_path}': {e}")
    
    return msg

def test_smtp_connection(config):
    """Test SMTP connection with detailed diagnostics"""
    client_name = config.get('supplier_name', 'Unknown')
    smtp_server = config['smtp_server']
    smtp_port = config['smtp_port']
    
    print(f"🔍 Testing SMTP connection for {client_name}...")
    print(f"   Server: {smtp_server}:{smtp_port}")
    
    try:
        # Test basic connectivity first
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # 10 second timeout
        result = sock.connect_ex((smtp_server, smtp_port))
        sock.close()
        
        if result != 0:
            print(f"❌ Cannot reach {smtp_server}:{smtp_port} - Server may be down or port blocked")
            return False
        else:
            print(f"✅ Server {smtp_server}:{smtp_port} is reachable")
            
    except Exception as e:
        print(f"❌ Network test failed: {e}")
        return False
    
    # Test SMTP connection
    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        
        print(f"✅ SMTP connection established")
        
        # Test login
        server.login(config['email_account'], config['password'])
        print(f"✅ SMTP authentication successful")
        
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ SMTP Authentication failed: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"❌ SMTP Connection error: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def connect_smtp(config):
    """Establish SMTP connection with better error handling"""
    try:
        if config['smtp_port'] == 465:
            server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        else:
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            server.starttls()
        
        server.login(config['email_account'], config['password'])
        return server
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ SMTP Authentication failed: {e}")
        return None
    except smtplib.SMTPConnectError as e:
        print(f"❌ SMTP Connection error: {e}")
        return None
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        return None
    except Exception as e:
        print(f"❌ SMTP connection failed: {e}")
        return None

def send_emails_for_client(config):
    """Send emails for a specific client configuration (thread-safe)"""
    thread_id = threading.current_thread().ident
    client_name = config['supplier_name']
    
    print(f"\n🔄 [Thread {thread_id}] Processing client: {client_name}")
    
    try:
        # Load template
        templates = load_template(config['templates'])
        if not templates:
            print(f"❌ [Thread {thread_id}] No templates found for {client_name}")
            return 0
        
        # Get attachments
        attachments = get_attachments(config['attachments'])
        if not attachments:
            print(f"⚠️ [Thread {thread_id}] No attachments found for {client_name}")
        else:
            print(f"📎 [Thread {thread_id}] Found {len(attachments)} attachment(s) for {client_name}")
        
        # Load mail data (thread-safe as pandas operations are generally thread-safe for reading)
        mail_data = load_mail_data()
        if mail_data.empty:
            print(f"❌ [Thread {thread_id}] No mail data available for {client_name}")
            return 0
        
        # Get already sent emails
        sent_emails = get_sent_emails(config['attachments'])
        print(f"📋 [Thread {thread_id}] Found {len(sent_emails)} previously sent emails for {client_name}")
        
        # Filter out already sent emails
        unsent_data = mail_data[~mail_data['Email'].str.lower().isin(sent_emails)]
        
        if DEBUG:
            # In debug mode, send only one email to specified address
            debug_data = unsent_data.head(1).copy()
            if not debug_data.empty:
                debug_data.loc[debug_data.index[0], 'Email'] = 'yashwanthsc1@gmail.com'
                debug_data.loc[debug_data.index[0], 'First Name'] = f'Debug User ({client_name})'
                # Set debug values for other common fields that might be in templates
                if 'Company' in debug_data.columns:
                    debug_data.loc[debug_data.index[0], 'Company'] = f'Debug Company Ltd ({client_name})'
                if 'Supplier' in debug_data.columns:
                    debug_data.loc[debug_data.index[0], 'Supplier'] = f'Debug Supplier ({client_name})'
                if 'Company Phone' in debug_data.columns:
                    debug_data.loc[debug_data.index[0], 'Company Phone'] = '+1-555-DEBUG'
                unsent_data = debug_data
            print(f"🔍 [Thread {thread_id}] DEBUG mode: sending only to yashwanthsc1@gmail.com for {client_name}")
        
        print(f"📧 [Thread {thread_id}] {len(unsent_data)} emails to send for {client_name}")
        
        if len(unsent_data) == 0:
            print(f"✅ [Thread {thread_id}] All emails already sent for {client_name}")
            return 0
        
        # Limit to client email limit (100 emails per client)
        emails_to_send = unsent_data.head(CLIENT_EMAIL_LIMIT)
        
        # Connect to SMTP
        server = connect_smtp(config)
        if not server:
            print(f"❌ [Thread {thread_id}] SMTP connection failed for {client_name}")
            return 0
        
        sent_count = 0
        batch_sent = 0
        
        for index, recipient in emails_to_send.iterrows():
            try:
                # Create and send message
                msg = create_message(config, templates, recipient, attachments)
                server.send_message(msg)
                
                # Save to sent list (thread-safe)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_sent_email(config['attachments'], recipient['Email'], timestamp)
                
                sent_count += 1
                batch_sent += 1
                
                print(f"[Thread {thread_id}] [{sent_count}/{len(emails_to_send)}] ✅ {client_name}: Sent to {recipient['Email']}")
                
                # Skip delay in debug mode
                if not DEBUG:
                    # Random delay between emails (30-60 seconds)
                    delay = random.uniform(30, 60)
                    time.sleep(delay)
                
                # Reconnect after every 40 emails to avoid timeout
                if batch_sent >= 40 and sent_count < len(emails_to_send):
                    print(f"🔄 [Thread {thread_id}] Reconnecting SMTP after 40 emails for {client_name}...")
                    server.quit()
                    server = connect_smtp(config)
                    if not server:
                        print(f"❌ [Thread {thread_id}] SMTP reconnection failed for {client_name}")
                        break
                    batch_sent = 0
                    
            except Exception as e:
                print(f"❌ [Thread {thread_id}] {client_name}: Failed to send to {recipient['Email']}: {e}")
        
        try:
            server.quit()
        except:
            pass  # Ignore errors when closing connection
            
        print(f"🏁 [Thread {thread_id}] Client '{client_name}': {sent_count} emails sent successfully")
        return sent_count
        
    except Exception as e:
        print(f"❌ [Thread {thread_id}] Error processing client '{client_name}': {e}")
        return 0

def test_all_smtp_connections():
    """Test SMTP connections for all clients"""
    print("🔧 Testing SMTP Connections for All Clients")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    configs = load_config()
    if not configs:
        print("❌ No valid configuration found. Exiting.")
        return
    
    all_working = True
    
    for config in configs:
        print(f"\n{'='*50}")
        if not test_smtp_connection(config):
            all_working = False
    
    print(f"\n{'='*50}")
    if all_working:
        print("✅ All SMTP connections are working!")
    else:
        print("❌ Some SMTP connections failed. Please check the configurations.")
    
    return all_working

def main():
    """Main function to process all clients in parallel"""
    import sys
    
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] == '--test-smtp':
        test_all_smtp_connections()
        return
    
    print("🚀 Starting Cold Mailing Application (Parallel Processing)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 Debug mode: {'ON' if DEBUG else 'OFF'}")
    print(f"📊 Client email limit: {CLIENT_EMAIL_LIMIT} emails per client")
    
    # Load configuration
    configs = load_config()
    if not configs:
        print("❌ No valid configuration found. Exiting.")
        return
    
    print(f"🔀 Processing {len(configs)} clients in parallel...")
    
    total_sent = 0
    results = {}
    
    # Use ThreadPoolExecutor to run clients in parallel
    with ThreadPoolExecutor(max_workers=len(configs)) as executor:
        # Submit all client tasks
        future_to_config = {
            executor.submit(send_emails_for_client, config): config 
            for config in configs
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_config):
            config = future_to_config[future]
            client_name = config.get('supplier_name', 'Unknown')
            
            try:
                sent_count = future.result()
                results[client_name] = sent_count
                total_sent += sent_count
                print(f"✅ Client '{client_name}' completed: {sent_count} emails sent")
                
            except Exception as e:
                print(f"❌ Client '{client_name}' failed with error: {e}")
                results[client_name] = 0
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 FINAL SUMMARY")
    print(f"{'='*60}")
    
    for client_name, sent_count in results.items():
        status = "✅" if sent_count > 0 else "❌"
        print(f"{status} {client_name}: {sent_count} emails sent")
    
    print(f"\n🎯 Total emails sent across all clients: {total_sent}")
    print("✨ Cold mailing session completed!")
    
    if DEBUG:
        print("\n🔍 Note: DEBUG mode was enabled - emails were sent to yashwanthsc1@gmail.com only")

if __name__ == '__main__':
    main()