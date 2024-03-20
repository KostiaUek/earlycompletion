import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import os
import glob

siteBase = "https://www.ceneo.pl"
siteBaseStart = "https://www.ceneo.pl/"
siteBaseEnd = "#tab=reviews"
file_path = "reviewed_products/"
paginationEnd = "/opinie-"


# test id = 158068053

def calculate_metrics(product_id):
    path = f'reviewed_products/{product_id}.json'
    if not os.path.exists(path):
        return None

    df = pd.read_json(path)
    opinions = len(df)
    disadvantages = len([array for array in df['negatives'].values if len(array) != 0])
    advantages = len([array for array in df['positives'].values if len(array) != 0])

    average_score = round(
        df['score'].str.split('/').apply(lambda x: float(x[0].replace(",", ".")) / int(x[1])).mean() * 5, 2)

    return {
        'opinions': opinions,
        'disadvantages': disadvantages,
        'advantages': advantages,
        'average_score': average_score
    }


def extract_product_ids():
    product_ids = []
    for file_name in glob.glob('reviewed_products/*.json'):
        product_id = file_name.replace('reviewed_products\\', '').replace(".json", "")
        if product_id:
            product_ids.append(product_id)
    return product_ids


def checkIfFileExists(product_id):
    json_file_path = file_path + product_id + ".json"
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
        print(type(data))
        print(len(data))
        return data
    return 0


def getSiteBody(product_id: str, socketio):
    # Checking if item was already found before
    check_path = checkIfFileExists(product_id)

    if bool(check_path):
        return check_path

    # If not, doing extraction
    link = siteBaseStart + product_id + siteBaseEnd
    response = requests.get(link)
    soup = BeautifulSoup(response.content, "html.parser")

    total_reviews_element = soup.find_all(class_="page-tab__title js_prevent-middle-button-click")[2]
    total_reviews = int(total_reviews_element.text.replace(")", "").replace("Opinie i Recenzje (", ""))

    if total_reviews > 500:
        total_reviews = 500

    print(total_reviews)

    review_elements = soup.find_all(class_="user-post user-post__card js_product-review")  # Reviews of the 1st page
    reviews = extractDataFromReviews(review_elements)

    if len(review_elements) == 10:
        anotherReviews = scrapePaginations(product_id, total_reviews, socketio)
        reviews += anotherReviews
    else:
        socketio.emit('progress_update', 100)

    json_path = file_path + f"{product_id}.json"
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump(reviews, file, ensure_ascii=False, indent=4)

    return reviews


def extractDataFromReviews(reviews: list):
    result = []
    for soup in reviews:

        opinion_id = soup["data-entry-id"]
        author_name_list = soup.find_all(class_="user-post__author-name")
        author_recommendation_list = soup.find_all(class_="user-post__author-recomendation")
        post_text_list = soup.find_all(class_="user-post__text")
        score_list = soup.find_all(class_="user-post__score-count")

        vote_yes_span = soup.find_all("span", id=f"votes-yes-{opinion_id}")
        vote_no_span = soup.find_all("span", id=f"votes-no-{opinion_id}")

        post_published = soup.find_all(class_="user-post__published")
        datetime = post_published[0].find_all("time")
        post_date = datetime[0]["datetime"]
        purchase_date = datetime[1]["datetime"] if len(datetime) > 1 else ""

        positives_list = []
        negatives_list = []
        columns = soup.find_all(class_="review-feature__col")

        for column in columns:
            if column.find_all(class_="review-feature__title review-feature__title--positives"):
                positives = column.find_all(class_="review-feature__item")
                for positive in positives:
                    positives_list.append(positive.text)
            else:
                negatives = column.find_all(class_="review-feature__item")
                for negative in negatives:
                    negatives_list.append(negative.text)

        author_name = author_name_list[0].text if len(author_name_list) > 0 else ""
        author_recommendation = author_recommendation_list[0].text if len(author_recommendation_list) > 0 else ""
        post_text = post_text_list[0].text if len(post_text_list) > 0 else ""
        score = score_list[0].text if len(score_list) > 0 else ""

        vote_yes_count = vote_yes_span[0].text if len(vote_yes_span) > 0 else 0
        vote_no_count = vote_no_span[0].text if len(vote_no_span) > 0 else 0

        negatives_number = len([array for array in negatives_list if len(array) != 0])
        positives_number = len([array for array in positives_list if len(array) != 0])

        res = {
            "opinion_id": opinion_id,
            "author_name": author_name,
            "author_recommendation": author_recommendation,
            "post_text": post_text,
            "score": score,
            "positives": positives_list,
            "negatives": negatives_list,
            "positives_count": positives_number,
            "negatives_count": negatives_number,
            "likes": vote_yes_count,
            "dislikes": vote_no_count,
            "post_time": post_date,
            "purchase_date": purchase_date,
        }
        result.append(res)
    return result


def scrapePaginations(product_id: str, target_scraped: int, socketio):
    result = []
    i = 2
    while True:
        url = siteBaseStart + product_id + paginationEnd + str(i)
        print("Extracting data from " + url)
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        isLast = not len(soup.find_all(class_="pagination__item pagination__next"))
        review_elements = soup.find_all(class_="user-post user-post__card js_product-review")
        parsedReviews = extractDataFromReviews(review_elements)
        result += parsedReviews

        total_scraped = i * 10
        percentage = round(total_scraped / target_scraped * 100, 3)
        socketio.emit('progress_update', percentage)

        if len(review_elements) < 10 or isLast:
            break
        i += 1
    return result


def checkPage(product_id: str):
    url = siteBaseStart + product_id + siteBaseEnd

    try:
        response = requests.get(url)
        if response.status_code != 200:
            return [False, ""]
        else:
            return [True, ""]
    except requests.exceptions.RequestException as e:
        return [False, str(e)]
