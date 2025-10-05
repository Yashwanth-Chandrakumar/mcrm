import os
import json
import csv
import smtplib
import time
import random
import threading
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import pandas as pd

# === Configuration ===
DEBUG = False
DEBUG_EMAIL = 'yashwanth2k05@gmail.com'  # Email for testing
DAILY_EMAIL_LIMIT = 100  # Per manufacturer
CONFIG_FILE = 'config.json'
MAILDATA_FILE = 'maildata.xlsx'

# Anti-spam measures
MIN_DELAY_SECONDS = 5  # Minimum delay between emails
MAX_DELAY_SECONDS = 20  # Maximum delay between emails

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

def get_sent_emails(manufacturer_name):
    """Get list of already sent email addresses for a manufacturer"""
    sent_file = os.path.join('sentdata', f"{manufacturer_name}.csv")
    sent_emails = set()
    
    if os.path.exists(sent_file):
        try:
            with open(sent_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if row:
                        sent_emails.add(row[0].strip().lower())
        except Exception as e:
            print(f"⚠️ Error reading sent emails file '{sent_file}': {e}")
    
    return sent_emails

def save_sent_email(manufacturer_name, email, timestamp):
    """Save sent email to CSV file (thread-safe)"""
    sent_file = os.path.join('sentdata', f"{manufacturer_name}.csv")
    
    with file_lock:
        os.makedirs('sentdata', exist_ok=True)
        file_exists = os.path.exists(sent_file)
        
        try:
            with open(sent_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['Email', 'Timestamp'])
                writer.writerow([email.lower(), timestamp])
        except Exception as e:
            print(f"❌ Error saving sent email to '{sent_file}': {e}")

def load_mail_data():
    """Load email data from Excel file"""
    try:
        df = pd.read_excel(MAILDATA_FILE)
        
        # Basic cleaning
        df.dropna(how='all', inplace=True)
        df.dropna(subset=['Email'], how='any', inplace=True)
        
        # Validate required columns
        if 'Company Name for Emails' not in df.columns:
            print("❌ Required column 'Company Name for Emails' not found in maildata.xlsx")
            print(f"Available columns: {', '.join(df.columns)}")
            return pd.DataFrame()
        
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
    if not attachments_folder:
        return []
        
    attachments_path = os.path.join('attachments', attachments_folder)
    attachment_files = []
    
    if os.path.exists(attachments_path):
        for file in os.listdir(attachments_path):
            file_path = os.path.join(attachments_path, file)
            if os.path.isfile(file_path):
                attachment_files.append(file_path)
    
    return attachment_files

def create_message(config, template, recipient_data, attachments):
    """Create email message with random template selection"""
    selected_template = random.choice(template)
    
    msg = MIMEMultipart('alternative')
    msg['From'] = config['email_account']
    msg['To'] = recipient_data['Email']
    msg['Subject'] = selected_template['subject']
    
    html_body = '\n'.join(selected_template['body'])
    
    # Replace placeholders
    for column in recipient_data.index:
        placeholder = f"{{{column.lower().replace(' ', '_')}}}"
        if placeholder in html_body:
            html_body = html_body.replace(placeholder, str(recipient_data[column]))
    
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

def connect_smtp(config):
    """Establish SMTP connection"""
    try:
        if config['smtp_port'] == 465:
            server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        else:
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            server.starttls()
        
        server.login(config['email_account'], config['password'])
        return server
    except Exception as e:
        print(f"❌ SMTP connection failed: {e}")
        return None

def select_emails_for_manufacturer(config, mail_data):
    """
    Select emails for a manufacturer using the correct algorithm:
    - One email per brand per day
    - Never repeat emails
    - Up to DAILY_EMAIL_LIMIT total
    - In DEBUG mode: Only select ONE email
    """
    manufacturer_name = config['supplier_name']
    print(f"\n{'='*60}")
    print(f"📊 Processing: {manufacturer_name}")
    print(f"{'='*60}")
    
    # DEBUG MODE: Only send one test email
    if DEBUG:
        print(f"🔍 DEBUG MODE: Selecting only ONE test email")
        test_recipient = mail_data.iloc[0].copy()
        test_recipient['Email'] = DEBUG_EMAIL
        test_recipient['First Name'] = 'Debug User'
        return [test_recipient]
    
    # Get sent emails for this manufacturer
    sent_emails = get_sent_emails(manufacturer_name)
    print(f"📝 Already sent to {len(sent_emails)} recipients")
    
    # Group by brand (Company Name for Emails)
    brands = mail_data.groupby('Company Name for Emails')
    print(f"🏢 Total brands in database: {len(brands)}")
    
    selected_recipients = []
    brands_with_unsent = 0
    brands_exhausted = 0
    
    # For each brand, select ONE unsent recipient
    for brand_name, brand_group in brands:
        # Filter out already-sent emails
        unsent_in_brand = brand_group[~brand_group['Email'].str.lower().isin(sent_emails)]
        
        if len(unsent_in_brand) == 0:
            brands_exhausted += 1
            continue
        
        brands_with_unsent += 1
        
        # Randomly select ONE person from this brand
        selected_recipient = unsent_in_brand.sample(n=1).iloc[0]
        selected_recipients.append(selected_recipient)
        
        # Stop if we've reached the daily limit
        if len(selected_recipients) >= DAILY_EMAIL_LIMIT:
            break
    
    print(f"\n📊 Selection Summary for {manufacturer_name}:")
    print(f"   Brands with unsent emails: {brands_with_unsent}")
    print(f"   Brands exhausted: {brands_exhausted}")
    print(f"   Emails selected: {len(selected_recipients)}")
    
    return selected_recipients

def send_emails_for_manufacturer(config, recipients):
    """Send emails for a specific manufacturer"""
    manufacturer_name = config['supplier_name']
    sent_count = 0
    failed_count = 0
    
    if not recipients:
        print(f"⚠️ No recipients to send for {manufacturer_name}")
        return 0, 0
    
    print(f"\n📤 Sending emails for {manufacturer_name}...")
    
    # Load templates
    templates = load_template(config['templates'])
    if not templates:
        print(f"❌ No templates found for {manufacturer_name}")
        return 0, len(recipients)
    
    # Get attachments
    attachments = get_attachments(config.get('attachments', ''))
    if attachments:
        print(f"📎 Attaching {len(attachments)} files")
    
    # Connect to SMTP
    server = connect_smtp(config)
    if not server:
        print(f"❌ Failed to connect SMTP for {manufacturer_name}")
        return 0, len(recipients)
    
    try:
        for i, recipient in enumerate(recipients, 1):
            email = recipient['Email'].strip()
            
            try:
                # Create and send message
                msg = create_message(config, templates, recipient, attachments)
                server.send_message(msg)
                
                # Save to sent list (skip in debug mode to avoid polluting data)
                if not DEBUG:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    save_sent_email(manufacturer_name, email, timestamp)
                
                sent_count += 1
                brand = recipient.get('Company Name for Emails', 'Unknown')
                print(f"✅ [{i}/{len(recipients)}] Sent to {email} ({brand})")
                
                # Anti-spam delay between emails
                if i < len(recipients):
                    if DEBUG:
                        delay = 2  # Short delay in debug mode
                    else:
                        # Random delay to appear more natural
                        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                    
                    print(f"⏳ Waiting {delay:.1f}s before next email...")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"❌ Failed to send to {email}: {e}")
                failed_count += 1
                
    finally:
        try:
            server.quit()
        except:
            pass
    
    return sent_count, failed_count

def process_manufacturer(config, mail_data):
    """Process a single manufacturer (for parallel execution)"""
    manufacturer_name = config['supplier_name']
    
    try:
        # Select recipients
        recipients = select_emails_for_manufacturer(config, mail_data)
        
        if not recipients:
            return {
                'manufacturer': manufacturer_name,
                'sent': 0,
                'failed': 0,
                'status': 'no_recipients'
            }
        
        # Send emails
        sent, failed = send_emails_for_manufacturer(config, recipients)
        
        return {
            'manufacturer': manufacturer_name,
            'sent': sent,
            'failed': failed,
            'status': 'completed'
        }
        
    except Exception as e:
        print(f"❌ Error processing {manufacturer_name}: {e}")
        return {
            'manufacturer': manufacturer_name,
            'sent': 0,
            'failed': 0,
            'status': f'error: {str(e)}'
        }

def main():
    """Main function"""
    print("🚀 Starting Cold Mailing Application")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 Debug mode: {'ON' if DEBUG else 'OFF'}")
    print(f"📊 Daily email limit per manufacturer: {DAILY_EMAIL_LIMIT}")
    
    # Load configuration
    configs = load_config()
    if not configs:
        print("❌ No valid configuration found. Exiting.")
        return
    
    print(f"📋 Total manufacturers configured: {len(configs)}")
    
    # Load mail data once
    mail_data = load_mail_data()
    if mail_data.empty:
        print("❌ No mail data available. Exiting.")
        return
    
    print(f"📧 Total emails in database: {len(mail_data)}")
    print(f"🏢 Total brands: {mail_data['Company Name for Emails'].nunique()}")
    
    # Process each manufacturer in parallel
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    print(f"\n{'='*60}")
    print("🚀 Starting parallel email campaigns...")
    print(f"{'='*60}\n")
    
    results = []
    with ThreadPoolExecutor(max_workers=len(configs)) as executor:
        futures = {
            executor.submit(process_manufacturer, config, mail_data): config
            for config in configs
        }
        
        for future in as_completed(futures):
            config = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"❌ Unexpected error for {config['supplier_name']}: {e}")
                results.append({
                    'manufacturer': config['supplier_name'],
                    'sent': 0,
                    'failed': 0,
                    'status': f'unexpected_error: {str(e)}'
                })
    
    # Print final summary
    print(f"\n{'='*60}")
    print("📊 FINAL SUMMARY")
    print(f"{'='*60}\n")
    
    total_sent = sum(r['sent'] for r in results)
    total_failed = sum(r['failed'] for r in results)
    
    for result in results:
        print(f"🏭 {result['manufacturer']}:")
        print(f"   ✅ Sent: {result['sent']}")
        print(f"   ❌ Failed: {result['failed']}")
        print(f"   Status: {result['status']}\n")
    
    print(f"{'='*60}")
    print(f"✅ Total sent: {total_sent}")
    print(f"❌ Total failed: {total_failed}")
    print(f"📧 Total processed: {total_sent + total_failed}")
    print("✨ Cold mailing session completed!")
    
    if DEBUG:
        print(f"\n🔍 DEBUG MODE: Test email sent to {DEBUG_EMAIL} only")
        print("⚠️ No emails were saved to sent history in debug mode")

if __name__ == '__main__':
    main()