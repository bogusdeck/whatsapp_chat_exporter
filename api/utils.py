import re
from datetime import datetime

def parse_chat(chat_file):
    from .index import ChatMessage
    pattern = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{1,2}:\d{1,2})(?:\s*|\u202F)?(AM|PM)?\] ([^:]+): (.+)"
    messages = []
    count = 0
    current_message = None  

    try:
        with open(chat_file, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()  

                match = re.match(pattern, line)
                if match:
                    if current_message:
                        messages.append(current_message)
                        count += 1

                    date, time, am_pm, sender, message = match.groups()

                    try:
                        timestamp = datetime.strptime(
                            f"{date} {time} {am_pm}".strip(), 
                            "%d/%m/%y %I:%M:%S %p" if am_pm else "%d/%m/%y %H:%M:%S"
                        )
                    except ValueError:
                        print(f"Failed to parse: {date} {time} {am_pm}")
                        continue

                    sender = "You" if sender == "." else sender.strip()

                    current_message = ChatMessage(
                        timestamp=timestamp,
                        sender=sender,
                        message=message.strip(),
                        media=[],
                        media_urls=[]
                    )

                elif "<attached:" in line:
                    media_file = line.split("<attached:")[1].strip(">\n").strip()
                    if current_message:
                        current_message.media.append(media_file)

                elif current_message:
                    if line:
                        current_message.message += f"\n{line}"
                    else:
                        messages.append(current_message)
                        current_message = None  

            if current_message:
                messages.append(current_message)
                count += 1

    except FileNotFoundError:
        print(f"Error: The file {chat_file} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    return sorted(messages, key=lambda x: x.timestamp), count
