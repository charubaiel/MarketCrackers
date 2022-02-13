import pandas as pd
import requests as r
import numpy as np
import os
import json
import logging
import argparse
import clickhouse_driver
from clickhouse_driver import Client


client = Client('85.193.83.20', user = 'crypto_etl', password = '0987654321',
                settings = {'use_numpy': True})

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--file",type=str, default='data/data.txt',
                    help="choose path to uploading txt json file")
args = parser.parse_args()

logging.basicConfig(format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.INFO,
                    filename=rf'update_db.log'
                    )



def query(q,url='http://85.193.83.20:8123'):
    return r.post(url=url,
            data=q.encode('utf-8'),
            auth=(os.getenv('CRYPTO_ETL_USER'),os.getenv('CRYPTO_ETL_PASSWORD')))



def upload_du(tmp,db = 'crypto.binancews_du'):
    tmp['b_first_q']=tmp['b'].explode().dropna().apply(lambda x: x[1] if x[1]!='0.00000000' else np.nan).groupby(level=0).first().astype(float)
    tmp['a_first_q']=tmp['a'].explode().dropna().apply(lambda x: x[1] if x[1]!='0.00000000' else np.nan).groupby(level=0).first().astype(float)

    tmp['b_first_p']=tmp['b'].explode().dropna().apply(lambda x: x[0] if x[1]!='0.00000000' else np.nan).groupby(level=0).first().astype(float)
    tmp['a_first_p']=tmp['a'].explode().dropna().apply(lambda x: x[0] if x[1]!='0.00000000' else np.nan).groupby(level=0).first().astype(float)

    tmp['diff_p']=tmp[['b_first_p','a_first_p']].diff(axis=1).iloc[:,-1]
    tmp['diff_q']=tmp[['b_first_q','a_first_q']].diff(axis=1).iloc[:,-1]

    tmp['is_seller_pres_bid']=tmp['b_first_q'].diff().apply(lambda x: x if x>0 else 0)
    tmp['is_buyer_pres_bid']=tmp[['b_first_q','b_first_p']].diff().apply(lambda x: abs(x['b_first_q']) *-1  if x['b_first_p'] <0 else 0,axis=1)

    tmp['is_seller_pres_ask']=tmp['a_first_q'].diff().apply(lambda x: x if x>0 else 0)
    tmp['is_buyer_pres_ask']=tmp[['a_first_q','a_first_p']].diff().apply(lambda x: abs(x['a_first_q']) *-1  if x['a_first_p'] <0 else 0,axis=1)
    


    for n_ticks in [10,500]:
        tmp[f'ticks_{n_ticks}'] = np.arange(0,tmp.shape[0]) // n_ticks
        tmp[f'ticks_{n_ticks}_dt'] = tmp.groupby(f'ticks_{n_ticks}')['E'].transform('first')

    du = tmp[['E', 's', 'ticks_500', 'ticks_500_dt', 'ticks_10', 'ticks_10_dt', 
         'b_first_q', 'a_first_q', 'b_first_p', 'a_first_p', 'diff_p', 'diff_q', 
         'is_seller_pres_bid', 'is_buyer_pres_bid', 'is_seller_pres_ask', 'is_buyer_pres_ask']]

    du.rename(columns = {'E': 'event_time', 's': 'symbol',
                        'b_first_q': 'bid_first_q', 'b_first_p': 'bid_first_p', 
                        'a_first_q': 'ask_first_q', 'a_first_p': 'ask_first_p'}, inplace = True)
    
    client.insert_dataframe(f'insert into {db} values', du)


def upload_trade(tmp,db='crypto.binancews_trade'):

    tmp['type'] = tmp['p'].astype(float).diff().where(lambda x: x!=0).fillna(method='ffill').mul(100).clip(-1,1).map({-1:'sell',1:'buy'})
    
    for n_ticks in [10,500]:
        tmp[f'ticks_{n_ticks}'] = np.arange(0,tmp.shape[0]) // n_ticks
        tmp[f'ticks_{n_ticks}_dt'] = tmp.groupby(f'ticks_{n_ticks}')['E'].transform('first')

    trade = tmp[['E', 's', 't', 'p', 'q', 'b', 'a', 'T', 
               'ticks_500', 'ticks_500_dt', 'ticks_10', 'ticks_10_dt', 
               'm', 'type']]
    trade.rename(columns =  {'E': 'event_time', 'T': 'trade_time', 's': 'symbol',
                         't': 'trade_id', 'p': 'price', 'q': 'quantity', 'b': 'buyer_order_id', 'a': 'seller_order_id',
                         'm': 'is_marker_maker',
                         }, inplace = True)
    client.insert_dataframe(f'insert into {db} values', trade)

if __name__=='__main__':

    client.execute(
        """
        create table if not exists crypto.binancews_du (
        event_time UInt64,
        symbol String,
        ticks_500 UInt64,
        ticks_500_dt UInt64,
        ticks_10 UInt64,
        ticks_10_dt UInt64,
        bid_first_q Float64,
        ask_first_q Float64,
        bid_first_p Float64,
        ask_first_p Float64,
        diff_p Float64,
        diff_q Float64,
        is_seller_pres_bid Float64,
        is_buyer_pres_bid Float64,
        is_seller_pres_ask Float64,
        is_buyer_pres_ask Float64)
        engine = MergeTree
        order by event_time;
        """)

    client.execute(
        """
        create table if not exists crypto.binancews_trade (
        event_time UInt64,
        symbol String,
        trade_id Float64,  
        price Float64,
        quantity Float64,
        buyer_order_id UInt64,      
        seller_order_id UInt64,
        trade_time UInt64,
        ticks_500 UInt64,       
        ticks_500_dt UInt64,
        ticks_10 UInt64,
        ticks_10_dt UInt64,
        is_marker_maker UInt64,
        type String)
        engine = MergeTree
        order by event_time;
        """)


    with open(args.file) as file:
        n=0
        tmp_list = []
        for i in file:
            n+=1
            try:
                    tmp_list.append(json.loads(i))
            except:
                    print(f'{n}th line broken')
                    logging.error(f'{n}th line broken')
                    pass
            if n % 200000 == 0:
                upload_du(pd.DataFrame(tmp_list).query('e=="depthUpdate"').dropna(axis=1))
                upload_trade(pd.DataFrame(tmp_list).query('e!="depthUpdate"').dropna(axis=1))
                
                logging.info('du_data :',query('''select 
                        max(toDateTime64(event_time/1000,1)) as max,
                        count() as events,
                        uniq(event_time) as uniq
                        from crypto.binancews_du
                        ''').text)
                        
                logging.info('trade_data :',query('''select 
                        max(toDateTime64(event_time/1000,1)) as max,
                        count() as events,
                        uniq(event_time) as uniq
                        from crypto.binancews_trade
                        ''').text)

                tmp_list = []