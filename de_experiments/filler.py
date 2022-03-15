import pandas as pd
import numpy as np
import time
from tqdm import tqdm
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-f', default='de_experiments/some_sample_stream.txt')
args = parser.parse_args()

filepath = args.f

def generate_govnodata(size=1000):
    df = pd.DataFrame()
    df['id'] = np.random.randint(1000,100000,size=size)
    df['type'] = np.random.choice(['A','B'],size=size)
    df['values'] = np.random.beta(np.random.randint(10,100),np.random.randint(10,100),size=size)
    return df

def write_govnodata(filepath):
    with open(filepath,mode='a') as w:
        for _ in tqdm(range(10)):
            time.sleep(0.01)
            w.writelines(generate_govnodata().to_json(lines=True,orient='records'))

if __name__ == '__main__':
    n=0
    while n <5:
        try:
            while pd.read_json(filepath.replace('stream',f'stream_{n}'),lines=True).shape[0]<200000:     
                write_govnodata(filepath.replace('stream',f'stream_{n}'))     
        except:
            n+=1
            with open(filepath.replace('stream',f'stream_{n}'),mode='a') as w:
                w.write('')
