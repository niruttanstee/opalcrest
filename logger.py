from datetime import datetime


async def log(class_name, guild_name: str, member_name: str, activity: str):
    """
        Prints formatted activity log with date and time.
    """
    time = datetime.now()
    formatted_time = time.strftime("%H:%M:%S")
    formatted_log = (f"{formatted_time} {class_name}:" +
                     f" {guild_name} - {member_name} {activity}.")
    print(formatted_log)
