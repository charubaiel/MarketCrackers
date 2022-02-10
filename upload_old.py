import pandas as pd
import requests as r
import numpy as np
import os
import json
import logging
import argparse




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

name_dict = {
  "E": 'event_time',
  "s": 'symbol',
  "t": 'trade_id',
  "p": "price",     
  "q": "quantity",       
  "b": 'buyer_order_id',
  "a": 'seller_order_id', 
  "T": 'trade_time', 
  "m": 'is_marker_maker'
}


def upload_du(tmp,db = 'crypto.du_data'):
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
    tmp.drop(['e','u','U','b','a'],axis=1,inplace=True)
    tmp=tmp.rename(columns=name_dict)
    
    sample = ','.join(tuple(tmp.apply(lambda x: str(tuple(x)),axis=1).to_list()))
    query(f'INSERT INTO {db} VALUES {sample}')


def upload_trade(tmp,db='crypto.trade_data'):
    tmp=tmp.drop(['e','M'],axis=1)
    tmp['type'] = tmp['p'].astype(float).diff().where(lambda x: x!=0).fillna(method='ffill').mul(100).clip(-1,1).map({-1:'sell',1:'buy'})
    tmp=tmp.rename(columns=name_dict)
    
    sample = ','.join(tuple(tmp.apply(lambda x: str(tuple(x)),axis=1).to_list()))
    query(f'INSERT INTO {db} VALUES {sample}')

if __name__=='__main__':

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
                
                logging.info('du_data :'+query('''select 
                        max(toDateTime64(event_time/1000,1)) as max,
                        count() as events,
                        uniq(event_time) as uniq
                        from crypto.du_data
                        ''').text)
                        
                logging.info('trade_data :'+query('''select 
                        max(toDateTime64(event_time/1000,1)) as max,
                        count() as events,
                        uniq(event_time) as uniq
                        from crypto.trade_data
                        ''').text)
                tmp_list = []