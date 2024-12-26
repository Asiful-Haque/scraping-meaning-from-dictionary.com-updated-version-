import pymysql  # or mysql.connector for MySQL
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import random
import json

# Database connection
connection = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='bdword_v3'
)


def get_words_from_db():
    cursor = connection.cursor()

    # Fetch the first word with added = 0
    cursor.execute("SELECT word FROM v3_simple_list_trial WHERE added = 0 LIMIT 1")
    word = cursor.fetchone()  # Fetch a single word (as a tuple)

    word_text = word[0]  # Extract the actual word from the tuple

    # Update the added column to 1 for this word
    cursor.execute("UPDATE v3_simple_list_trial SET added = 1 WHERE word = %s", (word_text,))
    connection.commit()

    return word_text  # Return the fetched word


# Function to insert the word and meaning into the database
def save_word_meaning_to_db(word, meaning):
    print(f"Saving: {word} - {meaning}")
    cursor = connection.cursor()

    # Convert the meaning dictionary to a JSON string
    meaning_json = json.dumps(meaning, ensure_ascii=False)

    query = "INSERT INTO v3_simple_list_trial_store (word, meaning) VALUES (%s, %s)"
    cursor.execute(query, (word, meaning_json))
    cursor.execute("UPDATE v3_simple_list_trial_store SET added = 1 WHERE word = %s", (word,))
    connection.commit()


def scrape_word_meaning(word, driver, retries=3):
    base_url = f"https://www.dictionary.com/browse/{word}"
    for attempt in range(retries):
        try:
            driver.get(base_url)

            # Wait until the relevant section is loaded
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'section.uLEIc6UAEiaBDDj6qSnO[data-type="part-of-speech-module"]'))
            )

            # Parse the page with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Find all sections with class 'uLEIc6UAEiaBDDj6qSnO' and data-type="part-of-speech-module"
            sections = soup.find_all(
                'section',
                class_='uLEIc6UAEiaBDDj6qSnO',
                attrs={'data-type': 'part-of-speech-module'}
            )

            results = []

            for section in sections:
                # Find all divs inside the section
                divs = section.find_all('div')
                for div in divs:
                    # Check if the current div is within a 'british-dictionary-entries-module' section
                    parent_section = div.find_parent('section', attrs={'data-type': 'british-dictionary-entries-module'})
                    if parent_section:
                        continue  # Skip this div as it is inside a british-dictionary-entries-module

                    # Extract text content from class 'S3nX0leWTGgcyInfTEbW'
                    s3n_div = div.find('div', class_='S3nX0leWTGgcyInfTEbW')
                    s3n_text = s3n_div.get_text(strip=True) if s3n_div else None

                    # Extract all list items from 'ol' with class 'lpwbZIOD86qFKLHJ2ZfQ E53FcpmOYsLLXxtj5omt'
                    ol_element = div.find('ol', class_='lpwbZIOD86qFKLHJ2ZfQ E53FcpmOYsLLXxtj5omt')
                    ol_text = [li.get_text(strip=True) for li in ol_element.find_all('li')] if ol_element else None

                    if s3n_text or ol_text:
                        results.append({
                            'Bold_text': s3n_text,
                            'List Items': ol_text
                        })

            if results:
                print(f"Found {len(results)} results for {word}")
                return results
            else:
                print(f"No matching content found for {word}")
                return [{"message": "No data found"}]

        except Exception as e:
            print(f"Failed to retrieve data for word: {word} on attempt {attempt + 1}\nError: {e}")
            if attempt < retries - 1:
                delay = random.uniform(3, 6)
                print(f"Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                return [{"message": "No data found"}]



# Setup Selenium WebDriver with custom options
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--disable-webgl')
chrome_options.add_argument('--headless')  # Run in headless mode
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--log-level=3')  # Suppress logs
chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36')

# Path to ChromeDriver for Windows
service = Service(r'C:\Users\User\Documents\Sourav\chromedriver-win64\chromedriver.exe')  # Adjust the path if needed
driver = webdriver.Chrome(service=service, options=chrome_options)


# Continuously process words until no unprocessed words are left
while True:
    word = get_words_from_db()  # Fetch one word with `added = 0`

    if not word:  # If no more words are left to process
        print("All words have been processed.")
        break

    print(f"Scraping meaning for word: {word}")
    meaning = scrape_word_meaning(word, driver)

    if meaning:
        # Save to database
        save_word_meaning_to_db(word, meaning)
        print(f"Saved: {word} - {meaning}")
    else:
        print(f"No meaning found for word: {word}")

    # Add a delay of 3 to 6 seconds between requests to avoid being blocked
    delay = random.uniform(3, 6)
    print(f"Waiting for {delay:.2f} seconds before the next request...")
    time.sleep(delay)

# Close the browser and database connection
driver.quit()
connection.close()
