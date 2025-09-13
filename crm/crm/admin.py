from django.contrib import admin
from .models import EmailAccount, Email, EmailFolder, EmailAttachment

@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'email_address', 'protocol', 'incoming_host', 'is_active', 'date_added')
    list_filter = ('protocol', 'is_active', 'auto_sync')
    search_fields = ('name', 'email_address', 'username')
    readonly_fields = ('date_added', 'last_sync')

@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'get_recipients_display', 'email_date', 'status', 'is_read')
    list_filter = ('status', 'account', 'is_read', 'is_important', 'is_starred')
    search_fields = ('subject', 'sender', 'recipient')
    readonly_fields = ('timestamp', 'message_id')
    
    def get_recipients_display(self, obj):
        recipients = obj.get_recipients_list()
        return ', '.join(recipients[:2]) + ('...' if len(recipients) > 2 else '')
    get_recipients_display.short_description = 'Recipients'

@admin.register(EmailFolder)
class EmailFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'folder_type', 'is_system')
    list_filter = ('folder_type', 'is_system')
    search_fields = ('name', 'account__name')

@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'email', 'content_type', 'size')
    list_filter = ('content_type',)
    search_fields = ('filename', 'email__subject')
