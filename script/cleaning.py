# %%
import pandas as pd
from sqlalchemy import create_engine, text
import numpy as np
import googlemaps
import re
from datetime import timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os
import requests
import time 
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from lxml import etree as et
from lxml import html
import telebot
from datetime import datetime

class TelebotNotifier:
    def __init__(self):
        self.bot_token = os.getenv('TELEBOT_TOKEN')
        self.chat_id = os.getenv('TELEBOT_CHAT_ID')
        self.bot = telebot.TeleBot(self.bot_token)

    def send_notification(self, message):
        try:
            self.bot.send_message(self.chat_id, message)
        except Exception as e:
            print(f"Failed to send notification. Error: {e}")
            
## DB connection Class
class DatabaseConnection:
    def __init__(self):
        self.engine = None
        self.connect()

    def connect(self):
        db_username = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        self.engine = create_engine(f'postgresql://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}')

    def dispose(self):
        if self.engine:
            self.engine.dispose()

    def fetch_data(self, table_name, row_limit=None):
        try:
            # Construct the base query
            query = f'SELECT * FROM {table_name} WHERE cleaned = FALSE'

            # Add the LIMIT clause if row_limit is specified
            if row_limit is not None and row_limit > 0:
                query += f' LIMIT {row_limit}'

            query += ';'  # Finalize the query with a semicolon

            # Execute the query and fetch the data
            df = pd.read_sql_query(query, con=self.engine)

            if len(df) == 0:
                raise Exception("No data to be cleaned")
            else:
                print(f"Number of rows fetched: {len(df)}")  # Debugging line

            return df
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def update_data(self, df):
        with self.engine.connect() as conn:
            with conn.begin():
                ids_to_update = ','.join(map(str, df[df['cleaned'] == False]['id'].tolist()))
                update_statement = text(f"""
                    UPDATE {os.getenv('DB_TABLE_NAME')}
                    SET cleaned = TRUE
                    WHERE id = ANY(SELECT unnest(string_to_array(:ids, ',')::bigint[]))
                """)
                conn.execute(update_statement, {'ids': ids_to_update})

    def append_data(self, df, table_name):
        df.to_sql(table_name, self.engine, if_exists='append', index=False)
    
    def trigger_dod(self):
        query = f'SELECT clean_processed_jobs();'
        conn.execute(query)


## Geocoder class
class Geocoder:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        self.gmaps_client = googlemaps.Client(key=self.api_key)
        print("Geocoder initialized with Google API Key.")

    def geocode_location(self, location, attempt=1, max_attempts=3):
        print(f"Attempting to geocode location: {location}, Attempt: {attempt}")

        if location == 'NULL' or 'remote' in location.lower():
            print(f"Invalid location: {location}")
            return None, None

        try:
            geocode_result = self.gmaps_client.geocode(location)
            if geocode_result:
                latitude = geocode_result[0]['geometry']['location']['lat']
                longitude = geocode_result[0]['geometry']['location']['lng']
                print(f"Geocoded location: {location}, Latitude: {latitude}, Longitude: {longitude}")
                return latitude, longitude
            else:
                print(f"No geocode results for location: {location}")
                return None, None
        except googlemaps.exceptions.Timeout:
            print("Request timeout. Retrying...")
            if attempt < max_attempts:
                time.sleep(1)
                return self.geocode_location(location, attempt + 1)
            else:
                print("Maximum attempts reached. Geocoding failed.")
                return None, None
        except googlemaps.exceptions.ApiError as e:
            print(f"API error: {e}")
            return None, None
        except googlemaps.exceptions.HTTPError as e:
            print(f"HTTP error: {e}")
            return None, None
        except googlemaps.exceptions.TransportError as e:
            print(f"Transport error: {e}")
            return None, None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None, None

class Browser:
    def __init__(self):
        self.browser = self.get_browser()
        

    def get_browser(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=3840,2160")  # Specify window size
        chrome_options.add_argument("--disable-gpu")  # This option is often recommended for headless
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Mimic a user-agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        # chrome_options.page_load_strategy = 'normal'
        # driver = Service('/usr/local/bin/chromedriver')
        browser = webdriver.Chrome(options=chrome_options)
        # browser.get("https://www.indeed.com/")
        return browser

    def get_dom(self, url):
        self.browser.get(url)
        page_content = self.browser.page_source
        product_soup = BeautifulSoup(page_content, 'html.parser')
        dom = et.HTML(str(product_soup))
        return dom

    def scrape_job_description(self, url):
        self.browser.get(url)
        html_content = self.browser.page_source
        tree = html.fromstring(html_content)
        job_description_div = tree.xpath('//div[@id="jobDescriptionText"]')[0]
    
        # Extract text from all child elements. This includes text within <p>, <ul>, and <li> tags.
        job_description_parts = job_description_div.xpath('.//text()')
        
        # Clean the job description parts from script and style tags content
        cleaned_parts = [part.strip() for part in job_description_parts if part.strip() and not part.startswith(('function','var','<!--'))]
        
        # Join the parts with a space
        job_description = ' '.join(cleaned_parts)
        
        return job_description

    def close(self):
        self.browser.close()

#%%
#  Other functions

def calculate_post_date(row):
    post_str = row['post_date']
    if 'Just posted' in post_str or 'Today' in post_str:
        return row['scrap_time'].date()
    elif 'day' in post_str:
        # Find the number of days using regex to avoid '30+' causing an error
        days_ago = int(re.search(r'\d+', post_str).group())
        return row['scrap_time'].date() - timedelta(days=days_ago)
    elif '30+' in post_str:
        # If the post date is "30+ days ago", we'll just subtract 30 days,
        # but this will be an approximation as the exact number of days is not specified.
        return row['scrap_time'].date() - timedelta(days=30)
    else:
        # If the format is unexpected, return None or some default value
        return None

def convert_to_annual(salary_str):
    print(f"Processing salary string: {salary_str}")  # Debugging line

    if pd.isna(salary_str):
        return np.nan  # Keep NaN values as they are

    # Extract numbers from salary string
    numbers = re.findall(r'[\d\,]+\.?\d*', salary_str)
    numbers = [float(num.replace(',', '')) for num in numbers]
    
    # If no numbers found, return NaN
    if not numbers:
        return np.nan
    
    # Determine the time period and calculate the annual salary accordingly
    if 'year' in salary_str:
        annual_salary = sum(numbers) / len(numbers)
    elif 'month' in salary_str:
        annual_salary = sum(numbers) / len(numbers) * 12
    elif 'hour' in salary_str:
        annual_salary = sum(numbers) / len(numbers) * 40 * 52
    elif 'week' in salary_str:
        annual_salary = sum(numbers) / len(numbers) * 52
    elif 'day' in salary_str:
        annual_salary = sum(numbers) / len(numbers) * 5 * 52
    else:
        print("Salary period not recognized, returning NaN")  # Debugging line
        return np.nan
    
    print(f"Calculated annual salary: {annual_salary}")  # Debugging line
    return annual_salary


# def scrape_job_description(browser, url):
#     browser.get_browser()
#     browser.get(url)
#     html_content = browser.get_dom(url)
#     tree = html.fromstring(html_content)
#     job_description_div = tree.xpath('//div[@id="jobDescriptionText"]')[0]

#     # Extract text from all child elements. This includes text within <p>, <ul>, and <li> tags.
#     job_description_parts = job_description_div.xpath('.//text()')

#     # Clean the job description parts from script and style tags content
#     cleaned_parts = [part.strip() for part in job_description_parts if part.strip() and not part.startswith(('function','var','<!--'))]

#     # Join the parts with a space
#     job_description = ' '.join(cleaned_parts)

#     return job_description


def process_data(df, geocoder, browser):
    
    df_no_duplicate = df.drop_duplicates(subset=['job_jk']).copy()
    df_no_duplicate.drop(columns=['job_keyword'], inplace=True)
    print("DataFrame shape after dropping duplicates:", df_no_duplicate.shape)  # Debugging line for duplicates

    df_no_duplicate['salary'].replace('Not available', np.nan, inplace=True)
    df_no_duplicate['salary'] = np.ceil(df_no_duplicate['salary'].apply(convert_to_annual)).astype('Int64')
    print("Sample data after salary conversion:\n", df_no_duplicate[['salary']].head())  # Debugging line for salary conversion

#     # Geocoding
#      # Geocoding
#    # Assuming df_no_duplicate is your DataFrame and geocoder is an instance of the Geocoder class
#     df_no_duplicate.loc[:, 'coords'] = df_no_duplicate['job_location'].apply(geocoder.geocode_location)
#     print(df_no_duplicate.head(5))
#     df_no_duplicate[['latitude', 'longitude']] = pd.DataFrame(df_no_duplicate['coords'].tolist(), index=df_no_duplicate.index)
#     df_no_duplicate.drop(columns=['coords'], inplace=True)
#     print(df_no_duplicate.head(5))
#     # Concatenate latitude and longitude into a geometry column
#     df_no_duplicate.loc[:, 'geom'] = df_no_duplicate.apply(lambda row: f"SRID=4326;POINT({row['longitude']} {row['latitude']})"
#                                     if pd.notna(row['longitude']) and pd.notna(row['latitude'])
#                                     else None, axis=1)
#     df_no_duplicate.drop(columns=['latitude', 'longitude'], inplace=True)
#     print(df_no_duplicate.head(5))
#     # Swap columns
#     df_no_duplicate.loc[:, 'job_location'] = df_no_duplicate['geom']
#     df_no_duplicate.drop(columns=['geom'], inplace=True)
#     print(df_no_duplicate.head(5))

    # Convert 'scrap_time' to datetime
    df_no_duplicate.loc[:, 'scrap_time'] = pd.to_datetime(df_no_duplicate['scrap_time'])

    # Apply the functions to the DataFrame
    df_no_duplicate.loc[:, 'actual_post_date'] = df_no_duplicate.apply(calculate_post_date, axis=1)
    df_no_duplicate.loc[:, 'post_date'] = df_no_duplicate['actual_post_date']
    df_no_duplicate.drop(columns=['actual_post_date'], inplace=True)

    # Add empty 'location_keyword' column
    df_no_duplicate.loc[:, 'location_keyword'] = ''

    # for index, row in df_no_duplicate.iterrows():
    #     time.sleep(2)
    #     try:
    #         job_description = browser.scrape_job_description(df_no_duplicate.at[index, 'job_link'])
    #         if job_description:
    #             df_no_duplicate.at[index, 'job_description'] = job_description
    #             print(f"Processed job description for row {index}")  # Debugging line for job description
    #     except Exception as e:
    #         print(f"Error processing job link at row {index}: {df_no_duplicate.at[index, 'job_link']}")
    #         print(f"Error details: {e}")  # Optionally, print the error details
    #         continue 
    #print(df_no_duplicate.head(5))
    df_no_duplicate.drop(columns=['cleaned'],inplace=True)
 #   print(df_no_duplicate.head(5))
    print(f"Number of rows after processing: {len(df_no_duplicate)}")  # Debugging line
    return df_no_duplicate

# def main():
#     load_dotenv()
#     print("Environment variables loaded.")  # Debugging line
#     db = DatabaseConnection()
#     print("Database connection established.")  # Debugging line
#     geocoder = Geocoder()
#     print("Geocoder initialized.")  # Debugging line
#     browser = Browser()
#     print("Browser initialized.")  # Debugging line
#     telegram_notifier = TelebotNotifier()
#     print("Telegram notifier initialized.")  # Debugging line
#     table_name = os.getenv('DB_TABLE_NAME')
#     try:
#         df = db.fetch_data(table_name)
#         print(f"Data fetched from table: {table_name}")  # Debugging line
#         df_unique = process_data(df, geocoder, browser)
#         print("Data processed.")  # Debugging line

#         db.update_data(df)
#         print("Data updated.")  # Debugging line
#         db.append_data(df_unique, 'processed_job')
#         print("Data appended.")  # Debugging line

def log_execution_time():
    with open("script_execution_log.txt", "a") as file:
        file.write(f"Script executed at {datetime.now()}\n")

def main():
    
    load_dotenv()
    print("Environment variables loaded.")  # Debugging line
    db = DatabaseConnection()
    print("Database connection established.")  # Debugging line
    geocoder = Geocoder()
    print("Geocoder initialized.")  # Debugging line
    browser = Browser()
    print("Browser initialized.")  # Debugging line
    telegram_notifier = TelebotNotifier()
    print("Telegram notifier initialized.")  # Debugging line
    table_name = os.getenv('DB_TABLE_NAME')
    
    try:
        df = db.fetch_data(table_name, row_limit=200)
        print(f"Data fetched from table: {table_name}")  # Debugging line
        df_unique = process_data(df, geocoder, browser)
        print("Data processed.")  # Debugging line

        db.update_data(df)
        print("Data updated.")  # Debugging line
        db.append_data(df_unique, 'processed_jobs')
        print("Data appended.")  # Debugging line

        db.dispose()
        print("Database connection disposed.")  # Debugging line
        telegram_notifier.send_notification(f"Cleaning completed. Number of rows processed: {len(df_unique)}")
        print("Notification sent.")  # Debugging line
    except Exception as e:
        print(f"Error: {e}")
        telegram_notifier.send_notification(f"Cleaning failed. Error: {e}")
        
if __name__ == "__main__":
    log_execution_time()
    main()