# ---------------------------------------- IMPORTS AND CONSTANTS ---------------------------------------- #
import os
import re
import time
import urllib.parse
import pandas as pd
from glob import glob
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
TEST_ID_FILE = 'test.txt'
TEST_INFO_FILE = 'test.csv'

# ---------------------------------------- ARGUMENT PARSING ---------------------------------------- #
ap = ArgumentParser(prog='LinkedIn_Scraper')
ap.add_argument('-c', '--chromedriver', action='store', default='chromedriver',
                help='Use this flag to pass to the program a path for chromedriver. Default is "./chromedriver".')
ap.add_argument('-t', '--test', action='store_true',
                help=f'Use this flag to run the script in test mode. In test mode, only the test files are edited.\
                      For example, running "python scraper.py --test --id --info" will read job ids from \
                      "{TEST_ID_FILE}" and only scrape info of those jobs and store in "{TEST_INFO_FILE}". Edit \
                      "{TEST_ID_FILE}" if you want to test on other job ids.')
ap.add_argument('--id', action='store_true',
                help='Use this flag to scrape new job ids and store in a new file with timestamp.')
ap.add_argument('--info', action='store_true',
                help='Use this flag to scrape information of jobs from the most recently scraped job id file.')
ap.add_argument('--manual-login', action='store_true',
                help='Use this flag to enter your login credentials through command line instead of file "login.txt".\
                      To use the file instead, make sure "login.txt" contains only 2 lines with your email/username\
                      on line 1 and password on line 2.')
args = vars(ap.parse_args())

# ---------------------------------------- DRIVER SETUP ---------------------------------------- #
options = Options()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--incognito')
options.add_argument('-disable-dev-shm-usage')

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


# ----------------------------------------  FUNCTIONS ---------------------------------------- #
# Scrape ID
def get_all_job_ids_from_page(driver, search_term, location_term, num_page=-1):
    # Preparing the search URL
    base_url = 'https://www.linkedin.com/jobs/search'
    keyword_url = f'keywords={urllib.parse.quote(search_term)}'
    location_url = f'location={urllib.parse.quote(location_term)}'
    url = f'{base_url}/?{keyword_url}&{location_url}&refresh=true'

    # Record the timestamp and start scraping
    job_id_scrape_time = datetime.now()
    print(f'DATE & TIME: {job_id_scrape_time.strftime("%Y/%m/%d %H:%M:%S")}')
    job_id_list = []
    driver.get(url)
    time.sleep(5)

    # Count total number of pages in the search result and setting the number of pages to scrape
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

    # Error printing (if there is any)
    if len(total_err_count) > 0:
        err_count_temp = ['Some jobs could not be scraped:']
        err_count_temp.extend([f' - {err[1]} jobs on page {err[0]}' for err in total_err_count])
        print('\n'.join(err_count_temp))
    else:
        print('All jobs scraped successfully.')

    # Remove dupes
    job_id_list = list(set(job_id_list))
    print(f'>>> Found total {len(job_id_list)} unique jobs.')

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
        'Apply Status': None,
        'HR URL': None,
        'Scrape Timestamp': datetime.now(),
        'Job Details': None,
        'Company Details': None
    }

    driver.get(info['Job URL'])
    time.sleep(3)

    # Job Name
    try:
        class_name = "jobs-unified-top-card__job-title"
        name = driver.find_element(By.CLASS_NAME, class_name).get_attribute("innerHTML")
        info['Name'] = name.strip()
    except NoSuchElementException:
        pass

    # Company
    try:
        css_selector = "span[class*='jobs-unified-top-card__company-name'] a"
        company = driver.find_element(By.CSS_SELECTOR, css_selector).get_attribute("innerHTML")
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
        pat = 'jobs-unified-top-card'
        css_selector = f"span[class*='{pat}__subtitle-primary-grouping'] span[class*='{pat}__bullet']"
        location = driver.find_element(By.CSS_SELECTOR, css_selector).get_attribute("innerHTML")
        info['Location'] = location.strip()
    except NoSuchElementException:
        pass

    # Workplace Type
    try:
        class_name = "jobs-unified-top-card__workplace-type"
        work_type = driver.find_element(By.CLASS_NAME, class_name).get_attribute("innerHTML")
        info['Workplace Type'] = work_type.strip()
    except NoSuchElementException:
        pass

    # Time Posted
    try:
        class_name = "jobs-unified-top-card__posted-date"
        time_posted = driver.find_element(By.CLASS_NAME, class_name).get_attribute("innerHTML")
        info['Time Posted'] = time_posted.strip()
    except NoSuchElementException:
        pass

    # Applicants Count
    try:
        pat = 'jobs-unified-top-card'
        css_selector = f"div[class*='mb2'] li[class*='{pat}__job-insight--highlight'] > span"
        applicants = driver.find_element(By.CSS_SELECTOR, css_selector).text
        app_counts = re.search(r'(\d+) applicants', applicants.lower())
        if app_counts is not None:
            info['Applicants Count'] = int(app_counts.group(1))
        else:
            raise NoSuchElementException
    except NoSuchElementException:
        try:
            pat = 'jobs-unified-top-card'
            css_selector = f"span[class*='{pat}__subtitle-secondary-grouping'] span[class*='{pat}__bullet']"
            applicants = driver.find_element(By.CSS_SELECTOR, css_selector).text
            app_counts = re.search(r'(\d+) applicants', applicants.lower())
            if app_counts is not None:
                info['Applicants Count'] = int(app_counts.group(1))
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

    # Apply Status
    try:
        css_selector = "div[class='jobs-apply-button--top-card'] button li-icon"
        apply_button = driver.find_element(By.CSS_SELECTOR, css_selector)
        apply_status = apply_button.get_attribute('type')
        if apply_status == 'linkedin-bug':
            info['Apply Status'] = 'Easy Apply'
        elif apply_status == 'link-external':
            info['Apply Status'] = 'External Link'
    except NoSuchElementException:
        try:
            css_selector = "div[class*='jobs-details-top-card__apply-error'] li-icon"
            apply_button = driver.find_element(By.CSS_SELECTOR, css_selector)
            if apply_button.get_attribute('type') == 'error-pebble-icon':
                info['Apply Status'] = 'Closed'
        except NoSuchElementException:
            pass

    # HR URL
    try:
        css_selector = "div[class*='hirer-card__hirer-information'] a"
        hr_url = driver.find_element(By.CSS_SELECTOR, css_selector).get_attribute('href')
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

    # Company details
    try:
        css_selector = "div[class='jobs-company__box'] p div"
        job_details = driver.find_element(By.CSS_SELECTOR, css_selector).get_attribute('innerHTML')
        pat = r'<!--(?=.*?-->).*?-->'
        job_details = re.sub(pat, '', job_details, flags=re.DOTALL)  # Remove all HTML comments
        info['Company Details'] = job_details.strip()
    except NoSuchElementException:
        pass

    return info


# Read ID file
def read_id_file(file_path):
    with open(file_path, 'r') as f:
        lines = [line.strip() for line in f.readlines()]

    line_is_id = False
    skip = 0
    while not line_is_id:
        line = lines[skip]
        try:
            jid = int(line)
            line_is_id = True
        except ValueError:
            skip += 1
    search_terms = lines[:skip]
    jid_list = lines[skip:]
    return search_terms, jid_list


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

# ---------------------------------------- SEARCHING & SCRAPING ---------------------------------------- #

# SCRAPING JOB IDS
if args['id']:
    # Getting searching parameters from input and sanitizing them
    SEARCH_TERM = input('Enter your job search keywords: ')
    LOCATION_TERM = input('Enter your job search location: ')
    NUM_PAGE = input('Enter number of pages to scrape: ')
    while True:
        try:
            NUM_PAGE = int(NUM_PAGE)
            break
        except ValueError:
            NUM_PAGE = input('    Please enter an integer: ')

    # Start scraping
    print('-'*10 + '> SCRAPING IDS <' + '-'*10)
    if not args['test']:
        job_id_list, job_scrape_timestamp = get_all_job_ids_from_page(DRIVER, SEARCH_TERM, LOCATION_TERM, num_page=NUM_PAGE)
    else:
        _, job_id_list = read_id_file(os.path.join(DIR_PROJECT, DIR_ID, TEST_ID_FILE))
        job_scrape_timestamp = datetime.now()

    # Writing job IDs to file
    id_file_name = f'jobs_{job_scrape_timestamp.strftime("%y%m%d_%H%M%S")}.txt'
    id_file_path = os.path.join(DIR_PROJECT, DIR_ID, id_file_name)
    if not args['test']:
        with open(id_file_path, 'w+') as f:
            id_file_str = '\n'.join([f'keywords={SEARCH_TERM}',
                                    f'location={LOCATION_TERM}'] + job_id_list)
            f.write(id_file_str)
    print(f'[{job_scrape_timestamp.strftime(r"%Y/%m/%d %H:%M:%S")}] Updated job list at {id_file_path}')


# SCRAPING JOB INFO
if args['info']:
    # Checking for most recent job ID files
    id_file_list = sorted(glob(os.path.join(DIR_PROJECT, DIR_ID, 'jobs_*.txt')))
    if args['test']:
        id_file_path = os.path.join(DIR_PROJECT, DIR_ID, TEST_ID_FILE)
    else:
        id_file_path = id_file_list[-1]  # Most recent file
    print('\n    '.join(['Most recent ID files'] + id_file_list[-5:]))
    use_most_recent_file = input(f'Continue with {os.path.basename(id_file_path)}? (y/n) ').lower()
    while True:
        if use_most_recent_file not in ('y', 'n'):
            use_most_recent_file = input(f'    Please enter "y" or "n": ')
        else:
            break

    # Check if continue
    if use_most_recent_file == 'n':
        print('Aborted scraping job info.')
    else:
        # Read most recent ID file
        _, job_id_list = read_id_file(id_file_path)
        print(f'Found {len(job_id_list)} jobs.')

        # Start scraping
        print('-'*10 + '> SCRAPING INFO <' + '-'*10)
        job_info_list = []
        for job_id in tqdm(job_id_list):
            try:
                job_info = get_single_job_info(DRIVER, job_id)
                job_info_list.append(job_info)
            except Exception as e:
                print(e)

        # Convert to DataFrame and write to CSV file
        job_df = pd.DataFrame(job_info_list)
        info_file_path = os.path.join(DIR_PROJECT, DIR_INFO, os.path.basename(id_file_path)[:-3] + 'csv')
        job_df.to_csv(info_file_path, index=False)
        print(f'Updated job info at {info_file_path}.')
        print('-'*5 + ' Sample first row ' + '-'*5)
        print(job_df.iloc[0])

# Finally close and quit webdriver
print('-' * 30)
DRIVER.quit()
print('Driver closed.')
print('DONE')