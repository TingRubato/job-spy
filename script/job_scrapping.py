from datetime import datetime
import os
import re
import time
import telebot
import psycopg2
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from lxml import etree as et
from psycopg2 import extras
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import argparse
from selenium.webdriver.chrome.service import Service

load_dotenv()

print("Loaded environment variables.")

class TelebotNotifier:
    def __init__(self):
        self.bot_token = os.getenv('TELEBOT_TOKEN')
        self.chat_id = os.getenv('TELEBOT_CHAT_ID')
        self.bot = telebot.TeleBot(self.bot_token)

    def send_notification(self, message):
        try:
            self.bot.send_message(self.chat_id, message)
            print(f"Notification sent: {message}")
        except Exception as e:
            print(f"Failed to send notification. Error: {e}")

class JobDatabase:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                dbname=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST'),
                port=os.getenv('DB_PORT')
            )
            print("Database connection established.")
            self.create_table()
            print("Database table checked/created.")
        except Exception as e:
            print(f"Error connecting to the database: {e}")

    def create_table(self):
        with self.conn.cursor() as cur:
            try:
                cur.execute(f"CREATE TABLE IF NOT EXISTS {os.getenv('DB_TABLE_NAME')} ("
                            "id SERIAL PRIMARY KEY,"
                            "post_date TEXT,"
                            "job_link TEXT,"
                            "job_title TEXT,"
                            "job_location TEXT,"
                            "company_name TEXT,"
                            "salary TEXT,"
                            "job_description TEXT,"
                            "job_type TEXT,"
                            "job_keyword TEXT,"
                            "scrap_time TIMESTAMPTZ"
                            ")")
                self.conn.commit()
                print("Database table created/exists.")
            except Exception as e:
                print(f"Error creating/checking table: {e}")

    def insert_record(self, record):
        with self.conn.cursor() as cur:
            try:
                cur.execute(f'''
                INSERT INTO {os.getenv('DB_TABLE_NAME')} (post_date, job_link, job_title, job_location, company_name, salary, job_description, job_type, job_keyword, scrap_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', record)
                self.conn.commit()
                print("Record inserted into database.")
            except Exception as e:
                print(f"Error inserting record into database: {e}")

    def close(self):
        try:
            self.conn.close()
            print("Database connection closed.")
        except Exception as e:
            print(f"Error closing database connection: {e}")

class Browser:
    def __init__(self):
        self.browser = self.get_browser()

    def get_browser(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        try:
            service = Service(ChromeDriverManager().install())
            browser = webdriver.Chrome(options=chrome_options, service=service)
            browser.get("https://indeed.com")
            time.sleep(10)
            print("Browser initialized and opened Indeed homepage.")
            return browser
        except Exception as e:
            print(f"Error initializing browser: {e}")
            return None

    def get_dom(self, url):
        try:
            self.browser.get(url)
            time.sleep(5)
            page_content = self.browser.page_source
            product_soup = BeautifulSoup(page_content, 'html.parser')
            dom = et.HTML(str(product_soup))
            print(f"DOM obtained for URL: {url}")
            return dom
        except Exception as e:
            print(f"Error getting DOM for URL {url}: {e}")
            return None

    def close(self):
        try:
            self.browser.close()
            print("Browser closed.")
        except Exception as e:
            print(f"Error closing browser: {e}")

class Job:
    def __init__(self, job):
        self.job = job

    def get_job_title(self):
        try:
            job_title = self.job.xpath(".//a[contains(@class, 'jcs-JobTitle')]/span/@title")[0]
        except IndexError:
            job_title = 'Not available'
        return job_title

    def get_company_name(self):
        try:
            company_name = self.job.xpath('.//span[@data-testid="company-name"]/text()')[0].strip()
        except IndexError:
            company_name = 'Not available'
        return company_name

    def get_post_date(self):
        try:
            # Attempt to extract the posting date using xpath to find the 'date' class and get its text content.
            # Adjust the xpath as needed if the structure is different.
            post_date = self.job.xpath('.//span[@class="date"]/text()')[0].strip()
        except IndexError:
            # If the span with class 'date' is not found or it doesn't contain any text, return 'Not available'
            post_date = 'Not available'
        return post_date

    def get_company_location(self):
        try:
            company_location = self.job.xpath('.//div[@data-testid="text-location"]/text()')[0].strip()
        except IndexError:
            company_location = 'Not available'
        return company_location

    def get_job_salary(self):
        try:
            job_salary = self.job.xpath('.//div[contains(@class, "salary-snippet-container")]/div[@data-testid="attribute_snippet_testid"]/text()')[0].strip()
        except IndexError:
            job_salary = 'Not available'
        return job_salary

    def get_job_type(self):
        try:
            job_type = self.job.xpath('//div[@class="metadata"]/div[@data-testid="attribute_snippet_testid"][not(ancestor::div[@class="metadata salary-snippet-container"])]/text()')[0].strip()
        except IndexError:
            job_type = 'Not available'
        return job_type

    def get_job_description(self):
        try:
            job_description_parts = self.job.xpath('.//div[@class="job-snippet"]/ul/li/text()')
            job_description = ' '.join([part.strip() for part in job_description_parts])
        except IndexError:
            job_description = 'Not available'
        return job_description

    def get_job_link(self):
        try:
            job_link = self.job.xpath(".//a[contains(@class, 'jcs-JobTitle')]/@href")[0]
        except IndexError:
            job_link = 'Not available'
        return job_link


def scrape_jobs(db, browser, job_keyword, location_keyword, job_search_radius):
    all_jobs = []
    for page_no in range(0, 100, 10):
        print(f"Scraping page number: {page_no//10 + 1}")
        url = pagination_url.format(job_keyword, location_keyword, job_search_radius, page_no)
        page_dom = browser.get_dom(url)
        jobs = page_dom.xpath('//div[@class="job_seen_beacon"]')
        all_jobs = all_jobs + jobs
    for job in all_jobs:
        print("Processing a job...")
        job_obj = Job(job)
        job_link = base_url + job_obj.get_job_link()
        print(f"Job Link: {job_link}")
        time.sleep(2)
        post_date = job_obj.get_post_date()
        print(f"Job Post Info: {post_date}")
        job_title = job_obj.get_job_title()
        print(f"Job Title: {job_title}")
        time.sleep(2)
        company_name = job_obj.get_company_name()
        print(f"Company Name: {company_name}")
        time.sleep(2)
        job_location = job_obj.get_company_location()
        print(f"Company Location: {job_location}")
        time.sleep(2)
        salary = job_obj.get_job_salary()
        print(f"Salary: {salary}")
        time.sleep(2)
        job_type = job_obj.get_job_type()
        print(f"Job Type: {job_type}")
        time.sleep(2)
        job_desc = job_obj.get_job_description()
        print(f"Job Description: {job_desc[:50]}...")  # printing first 50 characters
        time.sleep(2)
        record = (post_date, job_link, job_title, job_location, company_name, salary, job_desc, job_type, job_keyword, datetime.now())
        db.insert_record(record)
        print("Job processed and data written to database.")

def main():
    
    job_search_keyword = ['Software','Embedded','AI','BizOps','Developer','Machine+Learning','Data+Analyst','Robotic','Cloud','DevOps','Data+Science']
    location_search_keyword = ['St.+Louis','Seattle','Austin','Boston','Toronto','New+York','Los-Angeles','Atlanta','Denver']

    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description='Scrape job data from Indeed.')

    # Add command-line arguments
    parser.add_argument('--location', nargs='+', help='Location(s) for job search', default=location_search_keyword)
    parser.add_argument('--position', nargs='+', help='Position(s) for job search', default=job_search_keyword)

    # Parse the command-line arguments
    args = parser.parse_args()
    
    try:
        telebot_notifier.send_notification("Script started")
        db = JobDatabase()
        browser = Browser()

        # Iterate through the provided positions and locations
        for job_keyword in args.position:
            print(f"Searching for job keyword: {job_keyword}")
            for location_keyword in args.location:
                print(f"Searching in location: {location_keyword}")
                scrape_jobs(db, browser, job_keyword, location_keyword, job_search_radius)

        browser.close()
        db.close()
        telebot_notifier.send_notification("Script finished successfully")

    except Exception as e:
        error_message = f"An error occurred: {e}"
        print(error_message)
        telebot_notifier.send_notification(error_message)

job_search_radius = 100  # in miles

# define base and pagination URLs
base_url = 'https://www.indeed.com'
pagination_url = "https://www.indeed.com/jobs?q={}&l={}&radius={}&sort=date&start={}"
# paginaton_url = "https://www.indeed.com/jobs?q={}&l={}&radius={}"
if __name__ == "__main__":
    # Instantiate the TelebotNotifier
    telebot_notifier = TelebotNotifier()
    main()
