# -*- coding: utf-8 -*-
import os
import json
from datetime import datetime
import logging

import random
import requests
from bs4 import BeautifulSoup
from google.cloud import firestore
from google.cloud.exceptions import NotFound

def hello_world(request):
    check_yelp()
    return 'ok'

def stars(rating):
    s = []
    for i in range(0, 5):
        if i < rating:
            s.append('⭑')
        else:
            s.append('⭒')
    return ''.join(s)

def srcset_largest(srcset):
    splits = srcset.split(",")
    splits = [x.split(" ") for x in splits]
    splits = [(x[0], float(x[1].replace("x", ""))) for x in splits]
    splits.sort(key=lambda x: x[1])
    return splits[-1][0]

def shorten(content, length=200, suffix='…'):
    if len(content) <= length:
        return content
    else:
        return content[:length].rsplit(' ', 1)[0]+suffix

def get_last_review_id():
    db = firestore.Client()
    ref = db.collection(u'alan-b-reviews').document(u'last-review')
    try:
        doc = ref.get()
        return doc.get(u'id')
    except NotFound:
        return "kird5Pd_VHrzpMaBtkLAJQ"

def set_last_review_id(review_id):
    db = firestore.Client()
    ref = db.collection(u'alan-b-reviews').document(u'last-review')
    ref.set({u'id': review_id, u'time': datetime.now()})

def check_yelp():
    origin_url = os.getenv('ORIGIN_URL')
    slack_hook = os.getenv('SLACK_HOOK')
    channel = os.getenv('CHANNEL', '@jmhobbs')
    user_photos = [
        "https://s3-media3.fl.yelpcdn.com/photo/A_LeoiWDA8fgrraaCeJXhQ/ls.jpg",
        "https://s3-media3.fl.yelpcdn.com/photo/Adkmo5OBVuYgfxN03CmwWA/ls.jpg",
        "https://s3-media4.fl.yelpcdn.com/photo/ZWVd_xrIIYDidGOWUgunyw/ls.jpg",
        "https://s3-media4.fl.yelpcdn.com/photo/UFy4h39J8tvS-OOibJB8Pw/ls.jpg",
        "https://s3-media2.fl.yelpcdn.com/photo/3Mtv2fj35lWoATk-8Ly58Q/ls.jpg",
        "https://s3-media4.fl.yelpcdn.com/photo/nlsdk--SZJzuQyyIdMBoog/ls.jpg",
        "https://s3-media4.fl.yelpcdn.com/photo/LdXPoFex4g38nMp1qKnnWA/348s.jpg",
        "https://s3-media3.fl.yelpcdn.com/photo/HE3mI7u2BQZq52hcn2js7g/ls.jpg",
        "https://s3-media1.fl.yelpcdn.com/photo/1NAkwwB5CgovMd120-z2Jg/ls.jpg"
    ]

    logging.info("Getting last review ID")

    last_review_id = get_last_review_id()

    logging.info(last_review_id)

    logging.info("Getting origin URL: %s" % (origin_url,))
    r = requests.get(origin_url)
    if r.status_code != 200:
        raise Exception("Failed to fetch URL: %d", (r.status_code,))

    logging.info("Got content, parsing...")
    soup = BeautifulSoup(r.text, 'html.parser')

    new_review_id = None

    reviews = soup.select("ul.reviews")
    for review in reviews[0].select("div.review"):
        rid = review['data-review-id']
        if last_review_id == rid:
            logging.info("Found most recent review, stopping.")
            break

        if new_review_id is None:
            logging.info("New review ID: %s" % (rid,))
            new_review_id = rid

        logging.info("Found new review, extracting info!")

        photo = srcset_largest(review.select('a[data-analytics-label=biz-photo]')[0].select('img.photo-box-img')[0]['srcset'])
        name = review.select('a[data-analytics-label=biz-name]')[0].get_text()
        url = review.select('a[data-analytics-label=biz-name]')[0]['href']
        address = review.select('address')[0].get_text("\n", strip=True)
        content = review.select('div.review-content p')[0].get_text()
        rating = review.select('.rating-large')
        rating = float(rating[0]['title'].replace(' star rating', ''))
        full_url = "https://www.yelp.com%s?hrid=%s" % (url, rid)

        logging.info("Building slack message.")

        review = {
            "channel": channel,
            "username": "Alan B.",
            "icon_url": random.choice(user_photos),
            "attachments": [
                {
                    "title": name,
                    "title_link": full_url,
                    "text": stars(rating) + "\n" + shorten(content, 200),
                    "thumb_url": photo,
                    "footer": address,
                    "color": "#D0262A"
                }
            ]
        }

        logging.info("Sending to Slack!")
        requests.post(slack_hook, data = {'payload': json.dumps(review)})

    logging.info("new_review_id: %s" % (new_review_id,))

    if new_review_id is not None:
        logging.info("Updating firestore latest review ID.")
        set_last_review_id(new_review_id)
    else:
        logging.info("No new review ID")

if __name__ == "__main__":
    check_yelp()
