import os
import json
import re
import datetime
import io

# PRAW to interact with reddit
import praw
# NLP tools for sentiment analysis
from textblob import TextBlob
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
# Stock ticker symbol recognition
from pytickersymbols import PyTickerSymbols
# Boto to interact with AWS
import boto3

KNOWN_TICKERS = ['AMC','GME']

S3_RESULT_BUCKET = 'subreddit-sentiment'

nltk.data.path = ['/nltk_data']
stock_ticker_regex = re.compile(r"\b\$?[A-Z]{2,4}\b")
stock_data = PyTickerSymbols()
all_stocks = stock_data.get_all_stocks()

# create object for VADER sentiment function interaction
sia = SentimentIntensityAnalyzer()

reddit = praw.Reddit(client_id=os.environ['CLIENT_ID'],
                     client_secret=os.environ['CLIENT_SECRET'],
                     user_agent='subredditSentimentAnalysis')

# get 10 hot posts from the showerthoughts subreddit
top_posts = reddit.subreddit(os.environ['SUBREDDIT']).top(os.environ['TOP_OF_DURATION'], limit=int(os.environ['POST_LIMIT']))

# Sentiment analysis function for TextBlob tools
def text_blob_sentiment(review):
    analysis = TextBlob(review)
    if analysis.sentiment.polarity >= 0.0001:
        if analysis.sentiment.polarity > 0:
            return 'Positive'

    elif analysis.sentiment.polarity <= -0.0001:
        if analysis.sentiment.polarity <= 0:
            return 'Negative'
    else:
        return 'Neutral'
    

# sentiment analysis function for VADER tool
def nltk_sentiment(review):
    vs = sia.polarity_scores(review)
    if not vs['neg'] > 0.05:
        if vs['pos'] - vs['neg'] > 0:
            return 'Positive'
        else:
            return 'Neutral'

    elif not vs['pos'] > 0.05:
        if vs['pos'] - vs['neg'] <= 0:
            return 'Negative'
        else:
            return 'Neutral'
    else:
        return 'Neutral'


# replication of comment section of reddit post
def replies_of(top_level_comment, count_comment, ticker_sentiments):
    if len(top_level_comment.replies) == 0:
        count_comment = 0
        return
    else:
        for num, comment in enumerate(top_level_comment.replies):
            try:
                count_comment += 1
                print('-' * count_comment, comment.body)
                ticker_sentiment = find_ticker_sentiment_in_text(comment.body)
                if ticker_sentiment:
                    print("Found reply sentiment ", ticker_sentiment)
                    ticker_sentiments.append(ticker_sentiment)
            except:
                continue
            replies_of(comment, count_comment, ticker_sentiments)

def lookup_stock_ticker(ticker):
    print("Testing ticker:", ticker)
    if ticker in KNOWN_TICKERS:
        print("Exists")
        return True
    for stock in stock_data.get_all_stocks():
         if stock['symbol'] == ticker:
             return True
    print("Does not exist")
    return False

def get_sentiment_of_text(text):    
    text_blob_sent = text_blob_sentiment(text)
    nltk_sent = nltk_sentiment(text)
    return {
        'text_blob_sentiment': text_blob_sent,
        'nltk_sentiment': nltk_sent
    }

def find_ticker_sentiment_in_text(text):    
    # TODO: Match all the tickers in the text 
    print("Finding sentiment in ", text)
    match_result = stock_ticker_regex.search(text)
    if not match_result:
        print("No matches")
        return {}
    print("Testing ticker:", match_result.group(0))
    verified_stock_ticker = lookup_stock_ticker(match_result.group(0))
    if verified_stock_ticker:
        sentiment = get_sentiment_of_text(text)
        return {**{
            'ticker': match_result.group(0),
            }, **sentiment}
    else:
        return {}

def reduce_sentiment_results(ticker_sentiments):    
    reduced_results = {}
    for ticker_sentiment in ticker_sentiments:
        if ticker_sentiment['ticker'] in reduced_results.keys():
            update_sentiment_count(reduced_results[ticker_sentiment['ticker']], ticker_sentiment)
        else:
            reduced_results[ticker_sentiment['ticker']] = {
                'text_blob': 0,
                'nltk': 0
            }
    return reduced_results

def update_sentiment_count(reduced_result_entry, sentiment):
    if sentiment['text_blob_sentiment'] == 'Positive':
        reduced_result_entry['text_blob'] += 1
    elif sentiment['text_blob_sentiment'] == 'Negative':
        reduced_result_entry['text_blob'] -= 1

    if sentiment['nltk_sentiment'] == 'Positive':
        reduced_result_entry['nltk'] += 1
    elif sentiment['nltk_sentiment'] == 'Negative':
        reduced_result_entry['nltk'] -= 1

def handler(event, context):
    ticker_sentiments = []
    for submission in top_posts:
        print("Testing title ", submission.title)
        ticker_sentiment = find_ticker_sentiment_in_text(submission.title)
        if ticker_sentiment:
            print("Found title sentiment ", ticker_sentiment)
            ticker_sentiments.append(ticker_sentiment)
        
            
        submission_comm = reddit.submission(id=submission.id)
        for count, top_level_comment in enumerate(submission_comm.comments):
            print(f"-------------{count} top level comment start--------------")
            count_comm = 0
            print(top_level_comment.body)
            ticker_sentiment = find_ticker_sentiment_in_text(top_level_comment.body)
            if ticker_sentiment:
                print("Found top level comment sentiment ", ticker_sentiment)
                ticker_sentiments.append(ticker_sentiment)
 
            replies_of(top_level_comment,
                        count_comm,
                        ticker_sentiments)
        print(f"------------- End of submission --------------")

    reduced_results = reduce_sentiment_results(ticker_sentiments)    
    
    result_file_object = io.BytesIO(bytes(json.dumps(reduced_results).encode('utf-8')))
    
    result_file_name = "{}.json".format(datetime.datetime.utcnow().isoformat())
    s3_client = boto3.client('s3')
    s3_client.upload_fileobj(result_file_object, os.environ['RESULT_S3_BUCKET'], result_file_name)
    
    return {
        'statusCode': 200,
        'body': reduced_results
    }
