# ---------------------------------------- IMPORTS AND CONSTANTS ---------------------------------------- #
import os
import re
import time
import urllib.parse
import pandas as pd
from tqdm import tqdm
from getpass import getpass
from datetime import datetime
from argparse import ArgumentParser

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException

from linkedin_scraper import actions

DIR_PROJECT = os.path.dirname(os.path.realpath(__file__))
DIR_ID = 'job_id_dir'
DIR_INFO = 'job_info_dir'

# ---------------------------------------- ARGUMENT PARSING ---------------------------------------- #
ap = ArgumentParser(prog='LinkedIn_Scraper')
ap.add_argument('-c', '--chromedriver', action='store', default='chromedriver',
                help='Use this flag to pass to the program a path for chromedriver. Default is "./chromedriver".')
ap.add_argument('-t', '--test', action='store_true',
                help='Use this flag to run the script in test mode. In test mode, only the test files are edited.\
                      For example, running "python scraper.py --test --id --info" will read job ids from "test.txt" and\
                      only scrape info of those jobs and store in "test.csv". Edit "test.txt" if you want to test on\
                      other job ids.')
ap.add_argument('--id', action='store_true',
                help='Use this flag to scrape new job ids and store in a new file with timestamp.')
ap.add_argument('--info', action='store_true',
                help='Use this flag to scrape information of jobs from the most recently scraped job id file.')
ap.add_argument('--manual-login', action='store_true',
                help='Use this flag to enter your login credentials through command line instead of file "login.txt".\
                      To use the file instead, make sure "login.txt" contains only 2 lines with your email/username\
                      on line 1 and password on line 2.')
args = ap.parse_args()

# ---------------------------------------- DRIVER SETUP ---------------------------------------- #
options = Options()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--incognito')
options.add_argument('-disable-dev-shm-usage')
options.add_argument('--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"')

if args['chromedriver']:
    chromedriver_path = args['chromedriver']
else:
    chromedriver_path = os.path.join(DIR_PROJECT, 'chromedriver')

if not os.path.isfile(chromedriver_path):
    ERROR_CHROMEDRIVER = f'Could not find chromedriver at {chromedriver_path}. Please make sure that your chromedriver'\
                           'is in the same directory as this file.'
    raise Exception(ERROR_CHROMEDRIVER)

service = Service(chromedriver_path)
DRIVER = webdriver.Chrome(service=service, options=options)


# ---------------------------------------- SCRAPING FUNCTIONS ---------------------------------------- #
# Scrape ID
def get_all_job_ids_from_page(driver, search_term, location_term, num_page=-1):
    base_url = 'https://www.linkedin.com/jobs'
    keyword_url = f'keywords={urllib.parse.quote(search_term)}'
    location_url = f'location={urllib.parse.quote(location_term)}'
    url = f'{base_url}/?{keyword_url}&{location_url}&refresh=true'

    job_id_scrape_time = datetime.now()
    print(f'DATE & TIME: {job_id_scrape_time.strftime("%Y/%m/%d %H:%M:%S")}')
    job_id_list = []
    driver.get(url)
    time.sleep(5)

    # Count total number of pages in the search result
    max_page = driver.find_element(By.CLASS_NAME, 'jobs-search-results-list__pagination').find_element(By.TAG_NAME, 'ul').find_elements(By.TAG_NAME, 'li')[-1]
    max_page = int(max_page.text)
    num_page = min(max_page, num_page) if num_page > 0 else max_page
    print(f'Scraping {num_page} page(s) out of {max_page} total pages for {search_term} jobs in {location_term}...')
    total_err_count = []

    # Loop through num_page pages to scrape all products listed on each page
    for p in tqdm(range(1, num_page+1)):
        url = url + f'&start={(p-1)*25}'  # p=1: start=0, p=2: start = 25 ...
        driver.get(url)
        time.sleep(3)
        # Find all li tags that contain the job information
        products_all = driver.find_element(By.CLASS_NAME, "jobs-search-results-list").find_element(By.CLASS_NAME, "scaffold-layout__list-container").find_elements(By.CLASS_NAME, "scaffold-layout__list-item")

        err_count = 0
        for product in products_all:
            try:
                job_id = product.get_attribute("data-occludable-job-id")
                job_id_list.append(job_id)
            except NoSuchElementException:
                err_count += 1

        if err_count > 0:
            total_err_count.append((p, err_count))

    if len(total_err_count) > 0:
        err_count_temp = ['Some jobs could not be scraped:']
        err_count_temp.extend([f' - {err[1]} jobs on page {err[0]}' for err in total_err_count])
        print('\n'.join(err_count_temp))
    else:
        print('All jobs scraped successfully.')

    # Remove dupes
    job_id_list = list(set(job_id_list))
    print(f'---> Found total {len(job_id_list)} unique jobs.')

    return job_id_list, job_id_scrape_time


# Scrape INFO
def get_single_job_info(driver, job_id):

    info = {
        'Job ID': job_id,
        'Job URL': f"https://www.linkedin.com/jobs/view/{job_id}",
        'Name': None,
        'Company': None,
        'Company Logo URL': None,
        'Location': None,
        'Workplace Type': None,
        'Time Posted': None,
        'Applicants Count': None,
        'Job Overview': None,
        'Company Overview': None,
        'HR URL': None
    }

    driver.get(info['Job URL'])
    time.sleep(3)

    # Job Name
    try:
        name = driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__job-title").get_attribute("innerHTML")
        info['Name'] = name.strip()
    except NoSuchElementException:
        pass

    # Company
    try:
        company = driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__company-name").find_element(By.TAG_NAME, 'a').get_attribute("innerHTML")
        info['Company'] = company.strip()
    except NoSuchElementException:
        pass

    # Company Logo
    try:
        comp_logo_url = driver.find_element(By.CLASS_NAME, 'p5').find_element(By.TAG_NAME, 'img').get_attribute('src')
        info['Company Logo URL'] = comp_logo_url.strip()
    except NoSuchElementException:
        pass

    # Location
    try:
        location = driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__subtitle-primary-grouping").find_element(By.CLASS_NAME, "jobs-unified-top-card__bullet").get_attribute("innerHTML")
        info['Location'] = location.strip()
    except NoSuchElementException:
        pass

    # Workplace Type
    try:
        work_type = driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__workplace-type").get_attribute("innerHTML")
        info['Workplace Type'] = work_type.strip()
    except NoSuchElementException:
        pass

    # Time Posted
    try:
        time_posted = driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__posted-date").get_attribute("innerHTML")
        info['Time Posted'] = time_posted.strip()
    except NoSuchElementException:
        pass

    # Applicants Count
    try:
        applicants = driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__subtitle-secondary-grouping").find_element(By.CLASS_NAME, "jobs-unified-top-card__applicant-count").get_attribute("innerHTML")
        info['Applicants Count'] = applicants.strip()
    except NoSuchElementException:
        try:
            applicants = driver.find_element(By.CLASS_NAME, "jobs-unified-top-card__subtitle-secondary-grouping").find_element(By.CLASS_NAME, "jobs-unified-top-card__bullet").get_attribute("innerHTML")
            info['Applicants Count'] = applicants.strip()
        except NoSuchElementException:
            pass

    # Job & Company Insight
    try:
        overview_list = driver.find_elements(By.CLASS_NAME, "jobs-unified-top-card__job-insight")
        if len(overview_list) >= 2:
            overview_1, overview_2 = overview_list[:2]
        elif len(overview_list) == 1:
            overview_1, overview_2 = overview_list[0], None
        else:
            overview_1, overview_2 = None, None

        icon_job, icon_company = 'M17', 'M4'

        # Check overview icon
        def check_overview(overview):
            try:
                icon_path = overview.find_element(By.TAG_NAME, 'path').get_attribute('d')
                icon_pattern = icon_path.split()[0]
                if icon_pattern in (icon_job, icon_company):  # check if it is job or company icon
                    overview_text = overview.find_element(By.TAG_NAME, 'span').text  # use .text to get all information
                    pat = r'<!--(?=.*?-->).*?-->'
                    overview_text = re.sub(pat, '', overview_text, flags=re.DOTALL)  # Remove all HTML comments
                    return overview_text, icon_pattern
                else:
                    return None, None
            except NoSuchElementException:
                return None, None

        # Checking icons for job and company overview
        for overview in (overview_1, overview_2):
            ov, icon = check_overview(overview)
            if ov:
                if icon == icon_job:
                    info['Job Overview'] = ov.strip()
                elif icon == icon_company:
                    info['Company Overview'] = ov.strip()
    except NoSuchElementException:
        pass

    # HR URL
    try:
        hr_url = driver.find_element(By.CSS_SELECTOR, "div[class*='hirer-card__hirer-information'] a").get_attribute('href')
        info['HR URL'] = hr_url.strip()
    except NoSuchElementException:
        pass

    # Job details
    try:
        job_details = driver.find_element(By.ID, 'job-details').find_element(By.TAG_NAME, 'span').get_attribute('innerHTML')
        pat = r'<!--(?=.*?-->).*?-->'
        job_details = re.sub(pat, '', job_details, flags=re.DOTALL)  # Remove all HTML comments
        info['Job Details'] = job_details.strip()
    except NoSuchElementException:
        pass

    return info


# ---------------------------------------- LOGIN ---------------------------------------- #
if args['manual_login']:
    email = input('Email: ')
    password = getpass('Password: ')
else:
    try:
        with open('login.txt', 'r') as f:
            email, password = [line.strip() for line in f.readlines()[:2]]
    except IOError:
        ERROR_CREDENTIALS = 'Could not find "login.txt". Please put your login credentials in "login.txt" or use manual'\
                            ' login instead. Refer to the "--help" flag of this script for instructions on how to '\
                            'prepare "login.txt".'
        raise Exception(ERROR_CREDENTIALS)

print('Logging in...')
actions.login(DRIVER, email, password)
print('Login successful.')

SEARCH_TERM = input('Enter your job search keywords: ')
LOCATION_TERM = input('Enter your job search location: ')



