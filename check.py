import datetime

created_at = "2023-10-06T16:11:10Z"

release_time = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
now = datetime.datetime.now()  # Get the current time
time_difference = now - release_time
print(time_difference.days)