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

async def send_digest_email(user: User, digest_data: dict, suggested_reading: list[dict]) -> bool:
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

    # Build Suggested Reading Content
    if suggested_reading:
        html_content += "<h3>📚 Suggested Reading for Today</h3>"
        
        emoji_map = {
            "article": "📰",
            "youtube": "🎥",
            "github": "💻",
            "twitter": "💬",
            "linkedin": "💬",
            "pdf": "📄"
        }
        
        for item in suggested_reading:
            icon = emoji_map.get(item["content_type"], "📰")
            color = item["collection_color"] or "#64748b" # default slate
            title = item["title"] or "Untitled"
            title_html = f'<a href="{item["url"]}" style="color: #0f172a; text-decoration: none;">{title}</a>' if item["url"] else title
            read_time_html = f'<small style="color: #64748b;">(~{item["estimated_read_minutes"]} min read)</small>' if item["estimated_read_minutes"] else ''
            summary_html = f'<p style="margin: 6px 0 0 0; font-size: 14px; color: #475569;">{item["summary"]}</p>' if item["summary"] else ''
            
            html_content += f"""
            <div style="border-left: 3px solid {color}; padding: 8px 12px; margin-bottom: 12px; background: #f8fafc; border-radius: 0 4px 4px 0;">
                <div style="margin-bottom: 2px;">
                    <span style="margin-right: 4px;">{icon}</span>
                    <strong style="font-size: 15px;">{title_html}</strong> {read_time_html}
                </div>
                <div style="font-size: 11px; font-weight: bold; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;">
                    From: {item['collection_name']}
                </div>
                {summary_html}
            </div>
            """

    html_content += "<hr><p><small>Reply to this email has no effect. Manage your tasks at FlowDesk.</small></p>"

    try:
        # Note: Resend's python SDK is synchronous, so we execute it safely
        resend.Emails.send({
            "from": "FlowDesk <onboarding@resend.dev>",
            "to": [user.email],
            "subject": f"☀️ FlowDesk Morning Digest — {today_str}",
            "html": html_content
        })
        return True
    except Exception as e:
        print(f"Failed to send email to {user.email}: {e}")
        return False