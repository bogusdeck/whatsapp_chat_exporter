import re
from datetime import datetime

def parse_chat(chat_file):
    pattern = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{1,2}:\d{1,2})(?:\s*|\u202F)?(AM|PM)?\] ([^:]+): (.+)"
    messages = []

    try:
        with open(chat_file, 'r', encoding='utf-8-sig') as f:
            for line in f:
                match = re.match(pattern, line)
                if match:
                    date, time, am_pm, sender, message = match.groups()
                    
                    # Try parsing date and time in DD/MM/YY format
                    try:
                        timestamp = datetime.strptime(
                            f"{date} {time} {am_pm}".strip(), 
                            "%d/%m/%y %I:%M:%S %p" if am_pm else "%d/%m/%y %H:%M:%S"
                        )
                    except ValueError:
                        print(f"Failed to parse: {date} {time} {am_pm}")
                        continue
                    
                    # Mark messages from yourself as "You"
                    sender = "You" if sender == "." else sender.strip()

                    messages.append({
                        "timestamp": timestamp,  # Keep as datetime object
                        "sender": sender,
                        "message": message.strip(),
                        "media": None,
                    })
                elif "<attached:" in line:
                    media_file = line.split("<attached:")[1].strip(">\n").strip()
                    if messages:
                        messages[-1]["media"] = media_file

    except FileNotFoundError:
        print(f"Error: The file {chat_file} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Sort messages by timestamp (this can be omitted as it's sorted in get_messages)
    return sorted(messages, key=lambda x: x["timestamp"])
