from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from datetime import date, timedelta
from dateutil.parser import parse
from collections import Counter
import numpy as np
import requests
import csv
import re
import boto3
import os

stock_dict = Counter()


def grab_html():
    url = "https://www.reddit.com/r/wallstreetbets/search/?q=flair%3A%22Daily%20Discussion%22&restrict_sr=1&sort=new"
    driver = webdriver.Chrome(ChromeDriverManager().install())
    driver.get(url)

    return driver


def grab_link(driver):
    # Subtract one day from todays date
    yesterday = date.today() - timedelta(days=1)
    link = ""
    # Get all thread link texts, // - all html, * all possible objects
    # We want all objects with attribute 'class'
    links = driver.find_elements_by_xpath('//*[@class="_eYtD2XCVieq6emjKBH3m"]')
    for a in links:
        try:
            """
            Check if it's a DD or weekend thread
            Then split up text to only get last three parts
            Conver to datetime then compare to yesterdays date
            If equal, grab link from parent element
            """
            if a.text.startswith("Daily Discussion Thread"):
                # TODO: Search for date, account for edge case
                # e.g. "Daily Discussion Thread for January 27, 2021 - Part III"
                thread_date = "".join(a.text.split(" ")[-3:])
                parsed = parse(thread_date)
                if parse(str(yesterday)) == parsed:
                    link = a.find_element_by_xpath("../..").get_attribute("href")

            if a.text.startswith("Weekend"):
                weekend_date = a.text.split(" ")
                parsed_date = (
                    weekend_date[-3]
                    + " "
                    + weekend_date[-2].split("-")[1]
                    + weekend_date[-1]
                )
                parsed = parse(parsed_date)
                saturday = (
                    weekend_date[-3]
                    + " "
                    + str(int(weekend_date[-2].split("-")[1].replace(",", "")) - 1)
                    + " "
                    + weekend_date[-1]
                )

                # If Sunday or Saturday
                if parse(str(yesterday)) == parsed:
                    link = a.find_element_by_xpath("../..").get_attribute("href")
                elif parse(str(yesterday)) == parse(str(saturday)):
                    link = a.find_element_by_xpath("../..").get_attribute("href")
        except ValueError:
            pass

    try:
        # Grab only thread id
        stock_link = link.split("/")[-3]
        driver.close()
    except ValueError:
        stock_link = ""
        driver.close()

    return stock_link


def grab_commentid_list(stock_link):
    html = requests.get(
        f"https://api.pushshift.io/reddit/submission/comment_ids/{stock_link}"
    )
    raw_comment_list = html.json()

    return raw_comment_list


def grab_stocklist():
    stocks_list = []
    # If using API
    # stocks_list_nyse = requests.get(
    #     "https://dumbstockapi.com/stock?format=tickers-only&exchange=NYSE"
    # )
    # stocks_list.append(stocks_list_nyse.json())
    # stocks_list_nasdaq = requests.get(
    #     "https://dumbstockapi.com/stock?format=tickers-only&exchange=NASDAQ"
    # )
    # stocks_list.append(stocks_list_nasdaq.json())
    # Read CSV, get ticket from first column
    with open("tickers.csv", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            stocks_list.append(row[0])

    return stocks_list


def get_comments(comment_ids_list):
    comments = {}
    try:
        # Get each comment's body text
        html = requests.get(
            f"https://api.pushshift.io/reddit/comment/search?ids={comment_ids_list}&fields=body&size=500"
        )
        comments = html.json()
    except ValueError:
        print("error getting comments")
        pass

    return comments


def findWholeWord(w):
    return re.compile(r"\b({0})\b".format(w)).search
    # return re.compile(r"\b({0})\b".format(w), flags=re.IGNORECASE).search


def count_stock_tickers(comments_text, stocks_list):
    # print("counting", len(comments_text["data"]))
    # Count # of times ticket has been mentioned
    global stock_dict
    # Scan for each stock ticker in comment body then add to stock_dict
    for a in comments_text["data"]:
        for w in re.findall(r"\w+", a["body"]):
            if w in stocks_list:
                stock_dict[w] += 1
        # for ticker in stocks_list:
        #     # Check for whole words
        #     if findWholeWord(ticker)(a["body"]):
        #         stock_dict[ticker] += 1


def grab_stock_count(raw_comment_list, stocks_list):
    orig_list = np.array(raw_comment_list["data"])
    print(f"{len(orig_list)} ids")
    # Can only push 500 ids at a time
    comment_list = ",".join(orig_list[0:500])
    remove_me = slice(0, 500)
    cleaned = orig_list
    i = 0
    # Loop through array 500 each
    # Get comment text then count tickers
    while i < len(cleaned):
        print(len(cleaned))
        cleaned = np.delete(cleaned, remove_me)
        comments_ids_list = ",".join(cleaned[0:500])
        comments_text = get_comments(comments_ids_list)
        count_stock_tickers(comments_text, stocks_list)

    stocks = dict(stock_dict)
    return stocks


def write_csv(stock):
    """
    Access each stock ticker and value
    Invoke a sorted dictionary method to sort them alphanumerically first
    Then zip
    Create list of tuples
    """
    data = list(zip(sorted(stock.keys()), sorted(stock.values())))
    with open("/tmp/redditStocks.csv", "w") as w:
        writer = csv.writer(w, lineterminator="\n")
        writer.writerow(["Stock", "Number of Mentions"])
        for a in data:
            writer.writerow(a)


def upload_to_S3():
    s3 = boto3.client("s3")
    bucket = s3.Bucket(os.environ["BUCKET_NAME"])

    try:
        bucket.upload_file("/tmp/redditStocks.csv", "redditStocks.csv")
        print("Upload Successful")
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False


def main():
    driver = grab_html()
    print("Grabbing discussion id...")
    stock_link = grab_link(driver)
    print(stock_link)
    print("Grabbing comment ids...")
    comment_ids_list = grab_commentid_list("lbl62i")
    print("Grabbing stock list...")
    stocks_list = grab_stocklist()
    print("Gathering stocks from comments...")
    stocks = grab_stock_count(comment_ids_list, stocks_list)
    # print(stocks)
    print("Writing CSV...")
    write_csv(stocks)
    upload_to_S3()
    # Send SES: https://github.com/amazon-archives/serverless-app-examples/blob/master/python/ses-notification-python/lambda_function.py


if __name__ == "__main__":
    main()
