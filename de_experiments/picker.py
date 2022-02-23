import pandas as pd
import time
import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-f', default='de_experiments/')
args = parser.parse_args()

filepath = args.f
# Отправляет данные куда то, по хорошему тут должен быть процессинг + отправка в кх
def govnofunc(filepath):
    pd.read_json(filepath,lines=True).to_csv(f'{args.f}ttl_data.csv',mode='a')

if __name__ == '__main__':
# бесконечный луп по поиску нужных файликов.
    while 1==1:
        time.sleep(2)
        listdir = [i for i in os.listdir(filepath) if 'stream' in i]
        # Как только появляется файлик который не юзается основным скриптом, то мы его сразу процессим и тянем в бд
        if len(listdir)>0:
            for i in listdir:
                try:
                    govnofunc(filepath+i) # Вот эта функция может быть совсем любой
                    os.remove(filepath+i) # Удаляем файлик, чтобы не жрать много места. Т.о. у нас максимум будет всегда 2 файла, а в идеале 1
                    print(f'get_{i}')
                except:
                    print('w8 for data')
