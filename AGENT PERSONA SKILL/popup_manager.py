from notification_router import route_attention

def notify_user(title, body, on_click=None):
    """
    Legacy wrapper for notify_user. Now routes through the centralized hub.
    """
    route_attention(title, body, action_url=on_click)

if __name__ == "__main__":
    notify_user("Clawdbot", "Hey! I'm watching your deck. Talk to me!")
