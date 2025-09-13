"""
URL configuration for crm project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.mailbox_home, name='landing'),
    path('mailbox/', views.mailbox_home, name='mailbox_home'),
    path('mailbox/add/', views.add_account, name='add_account'),
    path('mailbox/<int:account_id>/', views.view_emails, name='view_emails'),
    path('mailbox/<int:account_id>/send/', views.send_email, name='send_email'),
    path('mailbox/<int:account_id>/fetch/', views.fetch_emails, name='fetch_emails'),
    path('mailbox/<int:account_id>/settings/', views.account_settings, name='account_settings'),
    path('mailbox/<int:account_id>/toggle/', views.toggle_account_status, name='toggle_account_status'),
    path('mailbox/<int:account_id>/email/<int:email_id>/', views.email_detail, name='email_detail'),
    path('mailbox/<int:account_id>/email/<int:email_id>/read/', views.mark_email_read, name='mark_email_read'),
    path('mailbox/<int:account_id>/email/<int:email_id>/star/', views.star_email, name='star_email'),
    path('mailbox/<int:account_id>/email/<int:email_id>/delete/', views.delete_email, name='delete_email'),
    # Bulk operations
    path('mailbox/<int:account_id>/bulk-mark-read/', views.bulk_mark_read, name='bulk_mark_read'),
    path('mailbox/<int:account_id>/bulk-mark-unread/', views.bulk_mark_unread, name='bulk_mark_unread'),
    path('mailbox/<int:account_id>/bulk-delete/', views.bulk_delete, name='bulk_delete'),
]
