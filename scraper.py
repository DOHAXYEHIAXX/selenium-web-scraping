import csv
import time
from pathlib import Path
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "https://www.naukrigulf.com"
SEARCH_URL = BASE_URL + "/data-engineer-jobs"

PAGES = 3

OUTPUT = (
    Path(__file__).resolve().parent
    / "output"
    / "data_engineer_jobs.csv"
)


def clean_text(text):
    return " ".join(text.split())


def create_driver():
    options = webdriver.ChromeOptions()

    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")

    options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)

    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', "
        "{get: () => undefined})"
    )

    return driver


def get_job_links(driver):

    links = driver.find_elements(By.TAG_NAME, "a")

    job_links = []
    seen = set()

    for link in links:

        try:
            href = link.get_attribute("href")
            title = clean_text(link.text)

            if not href or not title:
                continue

            href_lower = href.lower()

            # Job pages on Naukrigulf normally contain "job"
            if "job" not in href_lower:
                continue

            # Ignore obvious navigation links
            bad_words = [
                "login",
                "register",
                "services",
                "career-tips",
                "browse-jobs",
                "employers",
                "create-job-alert",
                "modify-search",
            ]

            if any(word in href_lower for word in bad_words):
                continue

            if len(title) < 5:
                continue

            if href not in seen:
                seen.add(href)

                job_links.append({
                    "title": title,
                    "url": href
                })

        except Exception:
            continue

    return job_links


def find_text_by_label(driver, labels):

    """
    Finds small pieces of text near labels such as:
    Company, Location, Experience.
    """

    elements = driver.find_elements(By.XPATH, "//*")

    for element in elements:

        try:

            text = clean_text(element.text)

            if not text:
                continue

            # Avoid huge containers
            if len(text) > 300:
                continue

            lower = text.lower()

            for label in labels:

                if label in lower:

                    # Check nearby parent text
                    try:
                        parent = element.find_element(
                            By.XPATH,
                            ".."
                        )

                        parent_text = clean_text(parent.text)

                        if (
                            parent_text
                            and len(parent_text) < 300
                            and parent_text.lower() != lower
                        ):
                            return parent_text

                    except Exception:
                        pass

        except Exception:
            continue

    return ""


def extract_description(driver):

    # Try specific description containers first

    selectors = [
        ".jd-content",
        ".job-description",
        "[class*='jd-content']",
        "[class*='jobDescription']",
        "[class*='job-description']",
    ]

    for selector in selectors:

        try:

            elements = driver.find_elements(
                By.CSS_SELECTOR,
                selector
            )

            for element in elements:

                text = clean_text(element.text)

                if len(text) > 100:
                    return text

        except Exception:
            continue

    # Look for a heading containing "Job Description"
    try:

        headings = driver.find_elements(
            By.XPATH,
            "//*[contains("
            "translate(text(), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), "
            "'job description')]"
        )

        for heading in headings:

            try:

                parent = heading.find_element(
                    By.XPATH,
                    ".."
                )

                text = clean_text(parent.text)

                if len(text) > 100:
                    return text

            except Exception:
                continue

    except Exception:
        pass

    return ""


def extract_job(driver, job):

    print()
    print("Scraping:", job["title"])

    company = ""
    location = ""
    experience = ""
    description = ""

    original_window = driver.current_window_handle

    try:

        driver.execute_script(
            "window.open(arguments[0], '_blank');",
            job["url"]
        )

        driver.switch_to.window(
            driver.window_handles[-1]
        )

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "body")
            )
        )

        time.sleep(3)

        # -------------------------------------------------
        # COMPANY
        # -------------------------------------------------

        company_selectors = [
            ".companyName",
            ".company-name",
            "[class='companyName']",
            "[class='company-name']",
        ]

        for selector in company_selectors:

            try:

                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    selector
                )

                for element in elements:

                    text = clean_text(element.text)

                    if text and len(text) < 150:
                        company = text
                        break

                if company:
                    break

            except Exception:
                continue

        # -------------------------------------------------
        # LOCATION
        # -------------------------------------------------

        location_selectors = [
            ".location",
            ".job-location",
            ".loc",
            "[class='location']",
            "[class='job-location']",
        ]

        for selector in location_selectors:

            try:

                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    selector
                )

                for element in elements:

                    text = clean_text(element.text)

                    if text and len(text) < 150:
                        location = text
                        break

                if location:
                    break

            except Exception:
                continue

        # -------------------------------------------------
        # EXPERIENCE
        # -------------------------------------------------

        experience_selectors = [
            ".experience",
            ".exp",
            ".job-experience",
            "[class='experience']",
            "[class='job-experience']",
        ]

        for selector in experience_selectors:

            try:

                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    selector
                )

                for element in elements:

                    text = clean_text(element.text)

                    if text and len(text) < 100:
                        experience = text
                        break

                if experience:
                    break

            except Exception:
                continue

        # -------------------------------------------------
        # FALLBACK LABEL SEARCH
        # -------------------------------------------------

        if not company:

            company = find_text_by_label(
                driver,
                ["company"]
            )

        if not location:

            location = find_text_by_label(
                driver,
                ["location", "job location"]
            )

        if not experience:

            experience = find_text_by_label(
                driver,
                ["experience", "years of experience"]
            )

        # -------------------------------------------------
        # DESCRIPTION
        # -------------------------------------------------

        description = extract_description(driver)

        # Never use the entire body as the description.
        # That was causing the previous CSV problem.

        print("Company:", company)
        print("Location:", location)
        print("Experience:", experience)
        print(
            "Description length:",
            len(description)
        )

        return {
            "Job Title": job["title"],
            "Company Name": company,
            "Job Location": location,
            "Required Experience": experience,
            "Full Job Description": description,
        }

    except Exception as error:

        print("Error:", error)

        return {
            "Job Title": job["title"],
            "Company Name": "",
            "Job Location": "",
            "Required Experience": "",
            "Full Job Description": "",
        }

    finally:

        if len(driver.window_handles) > 1:

            driver.close()

            driver.switch_to.window(
                original_window
            )


def scrape():

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    driver = create_driver()

    all_jobs = []
    seen_urls = set()

    try:

        for page in range(1, PAGES + 1):

            print()
            print("=" * 60)
            print("PAGE", page)
            print("=" * 60)

            url = (
                SEARCH_URL
                + "?k="
                + quote_plus("Data Engineer")
                + f"&page={page}"
            )

            print("Opening:", url)

            driver.get(url)

            time.sleep(6)

            print(
                "Page title:",
                driver.title
            )

            print(
                "Current URL:",
                driver.current_url
            )

            page_text = clean_text(
                driver.find_element(
                    By.TAG_NAME,
                    "body"
                ).text
            )

            if "Oops! Something went wrong" in page_text:

                print(
                    "WARNING: NaukriGulf returned "
                    "an error page."
                )

                continue

            jobs = get_job_links(driver)

            print(
                "Potential job links:",
                len(jobs)
            )

            for job in jobs:

                if job["url"] in seen_urls:
                    continue

                seen_urls.add(job["url"])

                data = extract_job(
                    driver,
                    job
                )

                all_jobs.append(data)

            print(
                "Total jobs collected:",
                len(all_jobs)
            )

    finally:

        driver.quit()

    # -----------------------------------------------------
    # SAVE CSV
    # -----------------------------------------------------

    fieldnames = [
        "Job Title",
        "Company Name",
        "Job Location",
        "Required Experience",
        "Full Job Description",
    ]

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(all_jobs)

    print()
    print("=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)

    print(
        "Total jobs collected:",
        len(all_jobs)
    )

    print(
        "CSV saved to:",
        OUTPUT
    )


if __name__ == "__main__":
    scrape()