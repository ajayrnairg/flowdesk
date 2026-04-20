import resend
from zoneinfo import ZoneInfo
from datetime import datetime
from core.config import settings
from models.user import User

# Initialize Resend
resend.api_key = settings.RESEND_API_KEY

def _build_task_html(tasks: list) -> str:
    """Helper to build list items for tasks."""
    html = "<ul>"
    for task in tasks:
        due_str = f" <em>(Due: {task.due_date})</em>" if task.due_date else ""
        html += f"<li><strong>[{task.priority.value}]</strong> {task.title}{due_str}</li>"
    html += "</ul>"
    return html

async def send_digest_email(user: User, digest_data: dict) -> bool:
    """
    Constructs and sends a clean HTML morning digest via Resend.
    Catches all exceptions to prevent crashing the orchestrator loop.
    """
    ist = ZoneInfo("Asia/Kolkata")
    today_str = datetime.now(ist).strftime("%A, %b %d, %Y")
    
    # Build HTML Content
    html_content = f"<h2>☀️ FlowDesk Morning Digest — {today_str}</h2>"
    
    if digest_data["overdue_tasks"]:
        html_content += "<h3>🚨 Overdue Tasks</h3>"
        html_content += _build_task_html(digest_data["overdue_tasks"])
        
    if digest_data["daily_tasks"]:
        html_content += "<h3>📅 Today's Focus (Daily)</h3>"
        html_content += _build_task_html(digest_data["daily_tasks"])
        
    if digest_data["weekly_tasks"]:
        html_content += "<h3>🗓️ This Week's Goals</h3>"
        html_content += _build_task_html(digest_data["weekly_tasks"])
        
    if digest_data["monthly_tasks"]:
        html_content += "<h3>🎯 This Month's Milestones</h3>"
        html_content += _build_task_html(digest_data["monthly_tasks"])

    html_content += "<hr><p><small>Reply to this email has no effect. Manage your tasks at FlowDesk.</small></p>"

    try:
        # Note: Resend's python SDK is synchronous, so we execute it safely
        resend.Emails.send({
            "from": "FlowDesk <notifications@yourdomain.com>", # Update with your verified domain
            "to": [user.email],
            "subject": f"☀️ FlowDesk Morning Digest — {today_str}",
            "html": html_content
        })
        return True
    except Exception as e:
        print(f"Failed to send email to {user.email}: {e}")
        return False