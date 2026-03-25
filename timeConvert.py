from datetime import datetime, timezone, timedelta

def gmt_to_est(gmt_time_str: str) -> str:
    # Input format: HH:MM (24-hour), interpreted as GMT/UTC
    gmt_dt = datetime.strptime(gmt_time_str, "%H:%M").replace(tzinfo=timezone.utc)

    # EST is always UTC-5
    est_tz = timezone(timedelta(hours=-5), name="EST")
    est_dt = gmt_dt.astimezone(est_tz)

    return est_dt.strftime("%H:%M")

if __name__ == "__main__":
    gmt_input = input("Enter GMT time (HH:MM): ").strip()
    est_time = gmt_to_est(gmt_input)
    print(f"EST time: {est_time}")