import re

def parse_chat(chat_file):
 
    SENDER_NAME = "."

    pattern = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}:\d{2})(?:\s*|\u202F)?(AM|PM)?\] ([^:]+): (.+)"
    messages = []

    with open(chat_file, 'r', encoding='utf-8-sig') as f:
        for line in f:
            match = re.match(pattern, line)
            if match:
                date, time, am_pm, sender, message = match.groups()
                timestamp = f"{date} {time} {am_pm}".strip()
                
                # Mark messages from yourself as "You"
                sender = "You" if sender == SENDER_NAME else sender

                messages.append({
                    "timestamp": timestamp,
                    "sender": sender.strip(),
                    "message": message.strip()
                })
            else:
                if messages:
                    messages[-1]["message"] += f"\n{line.strip()}"

    return messages

