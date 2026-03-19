import datetime
import pytz

def main() -> None:
    print("Hello, World!")


if __name__ == "__main__":
    main()
    est = pytz.timezone('US/Eastern')
    pst = pytz.timezone('US/Pacific')

    est_time = datetime.datetime.now(est)
    pst_time = est_time.astimezone(pst)

    print(f"Current time in EST: {est_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Equivalent time in PST: {pst_time.strftime('%Y-%m-%d %H:%M:%S')}")