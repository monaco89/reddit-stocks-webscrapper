from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from datetime import date, timedelta
from dateutil.parser import parse
from collections import Counter
import numpy as np
import requests
import csv
import pygsheets
import pandas


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
        print(a.text)
        try:
            # Check if it's a DD or weekend thread
            # Then split up text to only get last three parts
            # Conver to datetime then compare to yesterdays date
            # If equal, grab link from parent element
            if a.text.startswith("Daily Discussion Thread"):
                # TODO: Search for date, account for edge case
                # e.g. "Daily Discussion Thread for January 27, 2021 - Part III"
                thread_date = "".join(a.text.split(" ")[-3:])
                print(thread_date)
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

    # Grab only thread id
    print(link)
    # TODO: Error handling
    stock_link = link.split("/")[-3]
    driver.close()
    print(stock_link)
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


def get_comments(comment_list):
    html = requests.get(
        f"https://api.pushshift.io/reddit/comment/search?ids={comment_list}&fields=body&size=1000"
    )
    newcomments = html.json()
    return newcomments


def get_stock_list(newcomments, stocks_list):
    # Count # of times ticket has been mentioned
    stock_dict = Counter()
    # Scan for each stock ticker in comment body then add to stock_dict
    for a in newcomments["data"]:
        for ticker in stocks_list:
            if ticker in a["body"]:
                stock_dict[ticker] += 1
    return stock_dict


def grab_stock_count(stock_dict, raw_comment_list):
    orig_list = np.array(raw_comment_list["data"])
    # Can only push 1000 ids at a time
    comment_list = ",".join(orig_list[0:1000])
    remove_me = slice(0, 1000)
    cleaned = np.delete(orig_list, remove_me)
    i = 0
    while i < len(cleaned):
        print(len(cleaned))
        cleaned = np.delete(cleaned, remove_me)
        new_comments_list = ",".join(cleaned[0:1000])
        newcomments = get_comments(new_comments_list)
        get_stock_list(newcomments, stocks_list)
    stock = dict(stock_dict)
    return stock


def write_csv(stock):
    # Access each stock ticker and value
    # Invoke a sorted dictionary method to sort them alphanumerically first
    # Then zip
    # Create list of tuples
    data = list(zip(sorted(stock.keys()), sorted(stock.values())))
    with open("redditStocks.csv", "w") as w:
        writer = csv.writer(w, lineterminator="\n")
        writer.writerow(["Stock", "Number of Mentions"])
        for a in data:
            writer.writerow(a)


def output_to_google(stock):
    df = pd.fromdict(stock)
    gc = pygsheets.authorize(client_secret="client_secret_1.json")
    key = "xxxxxx"
    sheet = gc.open_by_key(key)
    worksheet = sheet.add_worksheet("Reddit Stock list")
    worksheet.set_dataframe(df, "A1")


if __name__ == "__main__":
    driver = grab_html()
    stock_link = grab_link(driver)
    comment_list = grab_commentid_list(stock_link)
    stockslist = grab_stocklist()
    newcomments = get_comments(comment_list)
    stock_dict = get_stock_list(new_comments, stocks_list)
    stock = grab_stock_count(stock_dict)
    write_csv(stock)
