from flask import Flask, render_template, request
app = Flask(__name__)
import quandl
quandl.ApiConfig.api_key = "2DaaDeZYy3iMCzUnxGgM"
import datetime
import pandas as pd
import numpy as np
import os
import pickle
from nltk import word_tokenize, pos_tag
import nltk
nltk.download('averaged_perceptron_tagger')
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from difflib import SequenceMatcher
import search_google.api

buildargs = {
  'serviceName': 'customsearch',
  'version': 'v1',
  'developerKey': 'AIzaSyClQNW9bvkEwRxWUEH2HRJpN58_k__BZuM'
}

cseargs = {
  'q': 'keyword query',
  'cx': '006579135136463128663:iaagthkidgk',
  'num': 4
}

url = "https://www.quandl.com/api/v3/datasets/ODA/POILWTI_USD.csv?start_date=2010-01-01"
df_oil = pd.read_csv(url, index_col=0, parse_dates=True)
oil_change_monthly =   np.log(df_oil['Value'].shift(1)) - np.log(df_oil['Value'])
oil_change_monthly = oil_change_monthly.dropna()
sorted = oil_change_monthly.sort_values()
df = sorted.iloc[-3:].to_frame()
df1 = sorted.iloc[:3].to_frame()


dataAMZN =  quandl.get("WIKI/AMZN", start_date="2012-01-01", end_date="2016-12-30")
dataMSFT = quandl.get("WIKI/MSFT", start_date="2012-01-01", end_date="2016-12-30")
dataAAPL = quandl.get("WIKI/AAPL", start_date="2012-01-01", end_date="2016-12-30")
dataNVDA = quandl.get("WIKI/NVDA", start_date="2012-01-01", end_date="2016-12-30")
df_index = pd.read_excel('PerformanceGraphExport.xls')
df_index = df_index.iloc[798:2055]
df_index = df_index.dropna()
df_index = df_index.rename(columns={'Effective date ': 'Date'})
df_index = df_index.set_index('Date')

stocks = pd.DataFrame({"AAPL": dataAAPL["Adj. Close"],
                      "MSFT": dataMSFT["Adj. Close"],
                      "AMZN" : dataAMZN["Adj. Close"],
                      "NVDA" : dataNVDA["Adj. Close"],
                      "INDEX" : df_index['S&P 500 Information Technology (Sector) (TR)']
                      })
stock_change = stocks.apply(lambda x: np.log(x) - np.log(x.shift(1)))
stock_change_dpr = stock_change * 100
tbill = quandl.get("USTREASURY/YIELD", start_date="2012-01-01", end_date="2016-12-30")
smcorr = stock_change_dpr.drop("INDEX", 1).corrwith(stock_change_dpr.INDEX)
sy = stock_change_dpr.drop("INDEX", 1).std()
sx = stock_change_dpr.INDEX.std()
x_bar_list = stock_change_dpr.INDEX.values[:1251] - tbill['3 MO'].values
beta = smcorr * sy / sx


def get_news_data(date):
    print('entered fetcher', date)
    news_data = []
    for year in date:
        for ls in os.listdir('data'):
                if ls.endswith('.pkl') and ls.startswith(year):
                    with open('data/' + ls, 'rb') as f:
                        data = pickle.load(f, encoding="latin1")
                        for datum in data:
                            if 'oil' in datum['title'].lower() or 'crude' in datum['title'] or 'WTI' in datum['title']:
                                news_data.append(datum)
    print('exiting fetcher')
    return news_data

def determine_tense_input(sentence):
    text = word_tokenize(sentence)
    tagged = pos_tag(text)

    tense = {}
    tense["future"] = len([word for word in tagged if word[1] == "MD"])
    tense["present"] = len([word for word in tagged if word[1] in ["VBP", "VBZ","VBG"]])
    tense["past"] = len([word for word in tagged if word[1] in ["VBD", "VBN"]])
    return(tense)

def get_month_news(date, sentiment):
    print('entered get_month_news', date)
    news_data = get_news_data([date])
    news_df = pd.DataFrame(news_data)
    news_df = news_df.drop('href', axis=1)
    news_df = news_df.drop_duplicates('title',False)
    news_df['tense'] = [ determine_tense_input(i) for i in news_df['title'].values]
    news = []
    sid = SentimentIntensityAnalyzer()
    for idx, item in news_df.iterrows():
        if len(news) == 0:
            if item['tense']['future'] > 0:
                    news.append(item['title'])
        else:
            if SequenceMatcher(a = item['title'], b = news[-1]).ratio() < 0.7:
                if item['tense']['future'] > 0:
                    ss = sid.polarity_scores(item['title'])
                    if ss[sentiment] > 0:
                        news.append(item['title'])
    return news

@app.route('/')
def hello_world():
    return render_template('index.html')

@app.route('/oil')
def oil():

    # df_oil['Value'].plot()
    return render_template('oil.html', html_data = df_oil.to_html(escape=False),
                           html_data1 = oil_change_monthly.to_frame().to_html(escape=False))

@app.route('/oil/1')
def oil1():
    return render_template('oil_next.html', df = df.to_html(escape=False),
                           df1=df1.to_html(escape=False))

@app.route('/oil/2')
def oil2():
    months = []
    mynewsgood = {}
    mynewsbad = {}
    for i, d in enumerate(sorted.index[:3]):
        t = str(d)[:4] + str(d)[5:7]
        mynewsbad[str(d)[:10]] = {
            'return' : sorted[i],
            'news' : get_month_news(t, 'neg')
        }
    for i, d in enumerate(sorted.index[-3:]):
        t = str(d)[:4] + str(d)[5:7]
        mynewsgood[str(d)[:10]] = {
            'return' : sorted[-i - 1],
            'news' : get_month_news(t, 'pos')
        }
    return render_template('oil_result.html', mynewsgood = mynewsgood,
                    mynewsbad = mynewsbad       )

@app.route('/tech')
def tech():
    return render_template('tech.html')

@app.route('/tech/1')
def tech1():
    return render_template('tech_next.html')

@app.route('/tech/2')
def tech2():
    ticker = request.args.get('ticker')
    y_bar_list = stock_change_dpr.drop("INDEX", 1)[ticker].values[:1251] - tbill['3 MO'].values
    temp = beta[ticker] * x_bar_list
    alpha = y_bar_list - temp
    df_alpha = pd.DataFrame(alpha).dropna().sort_values(by=0)
    top_3 = df_alpha.iloc[-3:]
    bottom_3 = df_alpha.iloc[:3]
    data = {'MSFT' : dataMSFT, 'AAPL' : dataAAPL , 'AMZN' : dataAMZN, 'NVDA' : dataNVDA}
    company_name = {
        'MSFT' : 'microsoft', 'AAPL' : 'apple' , 'AMZN' : 'amazon', 'NVDA' : 'nvidia'
    }
    top = {}

    for idx,x in top_3.iterrows():
        date = str(data[ticker].iloc[idx].name)[:10]
        q =  date + ' ' + company_name[ticker] + ' ' + 'news'
        print(q)
        top[date]={
            "alpha":x[0],
            "news_links" : search_google.api.results(buildargs, {
                'q' : q,
                'cx': cseargs['cx'],
                'num': 4
                }).get_values('items', 'link')
            }
    bottom = {}
    for idx,x in bottom_3.iterrows():
        date = str(dataMSFT.iloc[idx].name)[:10]
        q =  date + ' ' + company_name[ticker] + ' ' + 'news'
        print(q)
        bottom[date]={
            "alpha":x[0],
            "news_links" : search_google.api.results(buildargs, {
                'q' : q,
                'cx': cseargs['cx'],
                'num': 4
                }).get_values('items', 'link')
            }

    print(top, bottom)

    return render_template('tech_stock.html', ticker=ticker, top=top, bottom=bottom)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
