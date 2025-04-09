# Licensed to the Apache Software Foundation (ASF) under one

# or more contributor license agreements.  See the NOTICE file

# distributed with this work for additional information

# regarding copyright ownership.  The ASF licenses this file

# to you under the Apache License, Version 2.0 (the

# "License"); you may not use this file except in compliance

# with the License.  You may obtain a copy of the License at

#

#   http://www.apache.org/licenses/LICENSE-2.0

#

# Unless required by applicable law or agreed to in writing,

# software distributed under the License is distributed on an

# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY

# KIND, either express or implied.  See the License for the

# specific language governing permissions and limitations

# under the License.

"""

### Tutorial Documentation

Documentation that goes along with the Airflow tutorial located

[here](https://airflow.apache.org/tutorial.html)

"""


from __future__ import annotations


# [START tutorial]

# [START import_module]

import textwrap

import psycopg2 

from datetime import datetime, timedelta

import yfinance as yf
# The DAG object; we'll need this to instantiate a DAG

from airflow.models.dag import DAG
from airflow.utils.dates import days_ago
import os 
# Operators; we need this to operate!

#from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
#from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator 
#from airflow.operators.email.operator import EmailOperator

# [END import_module]

def download_price(**context): 

    # 从 context 中获取宏值
    ds = context['ds']
    ds_nodash = context['ds_nodash']
    next_ds = context['next_ds']
    yesterday_ds = context['yesterday_ds']
    tomorrow_ds = context['tomorrow_ds']
    
    print(f"Execution Date is {ds}, {ds_nodash}")
    print(f"Next DS: {next_ds}")
    print(f"Yesterday DS: {yesterday_ds}")
    print(f"Tomorrow DS: {tomorrow_ds}") 
    
    stock_list_json = Variable.get("stock_list_json", deserialize_json=True) 
    valid_tickers = []
    if not stock_list_json:
        raise ValueError("stock_list_json is empty or invalid")

    for ticker in stock_list_json: 
        msft = yf.Ticker(ticker) 
        hist = msft.history(period="1mo")
        
        if hist.shape[0] > 0: 
            valid_tickers.append(ticker) 
        else: 
            continue 

        with open(get_file_path(ticker), 'w') as writer: 
            hist.to_csv(writer, index=True) 

        print("Downloaded "+ticker)

    return valid_tickers

#download_price()

def get_file_path(ticker): 
    return f'/home/gloria/workspace/airflow/logs/{ticker}.csv'

def load_price_data(ticker): 
    try: 
        file_path = get_file_path(ticker)
        with open(file_path, 'r') as reader: 
            lines = reader.readlines() 
            result = [[ticker] + line.split(',')[:5] for line in lines if line.strip() and line[:4] != 'Date'] 
            if not result: 
                print(f"Warning: No valid data found in {file_path}")
                return []
            return result
    except FileNotFoundError: 
        print(f"Error: File not found for {ticker}")
        return []
    except Exception as e:
        print(f"Error loading {ticker}: {str(e)}")
        return []


def save_to_mysql_stage(*args, **context):
    # tickers = get_tickers(context)
    # Pulls the return_value XCOM from "pushing_task"
    #tickers = context['ti'].xcom_pull(task_ids='download_prices')
    
    # stock_list_json = Variable.get("stock_list_json", deserialize_json=True) 
    tickers = context['ti'].xcom_pull(task_ids='download_price')
    print(f"received tickers: {tickers}")
    
    '''
    mydb = psycopg2.connect(
    host="localhost",
    user="airflow_user",
    password="airflow_pass",
    database="demodb",
    port=5432
    )
    '''
    from airflow.hooks.base_hook import BaseHook 
    conn = BaseHook.get_connection('demodb') 

    mydb = psycopg2.connect(
        host=conn.host, 
        user=conn.login, 
        password=conn.password, 
        database=conn.schema, 
        port=conn.port
    )

    mycursor = mydb.cursor()
    for ticker in tickers: 
        val = load_price_data(ticker)
        if not val or len(val) == 0:  # 检查是否为空
            print(f"Error: No data loaded for {ticker}")
            continue
        if len(val[0]) < 6:  # 检查每行是否有足够字段
            print(f"Error: Invalid data format for {ticker}, got {val[0]}")
            continue
        
        print(f"{ticker} length={len(val)}   {val[1]}")

        sql = """INSERT INTO stock_prices_stage
            (ticker, as_of_date, open_price,high_price, low_price, close_price) 
            VALUES (%s, %s, %s, %s, %s, %s)"""
        mycursor.executemany(sql, val)

        mydb.commit()

        print(mycursor.rowcount, "record inserted.")
    
    mydb.close()



with DAG(

    dag_id="Download_Stock_Price",

    default_args={

        "depends_on_past": False,

        "email": ["airflow@example.com"],

        "email_on_failure": False,

        "email_on_retry": False,

        "retries": 1,

        "retry_delay": timedelta(minutes=5),

        # 'queue': 'bash_queue',

        # 'pool': 'backfill',

        # 'priority_weight': 10,

        # 'end_date': datetime(2016, 1, 1),

        # 'wait_for_downstream': False,

        # 'sla': timedelta(hours=2),

        # 'execution_timeout': timedelta(seconds=300),

        # 'on_failure_callback': some_function, # or list of functions

        # 'on_success_callback': some_other_function, # or list of functions

        # 'on_retry_callback': another_function, # or list of functions

        # 'sla_miss_callback': yet_another_function, # or list of functions

        # 'on_skipped_callback': another_function, #or list of functions

        # 'trigger_rule': 'all_success'

    },

    # [END default_args]

    description="Download stock price and save to local csv files. ",

    #schedule=timedelta(days=1),
    schedule_interval='52 18 * * *',

    start_date=days_ago(2),

    catchup=False,
    max_active_runs=1,

    tags=["data"],

) as dag:

    # [END instantiate_dag]


    # [END basic_task]

    dag.doc_md = """

    This is a documentation placed anywhere

    """  # otherwise, type it like this
    download_task = PythonOperator(
        task_id = "download_price", 
        python_callable = download_price 
    )
    save_to_mysql_task =PythonOperator(
        task_id='save_to_database',
        python_callable=save_to_mysql_stage,
    )
    postgresql_task = SQLExecuteQueryOperator(
        task_id = 'merge_stock_price', 
        conn_id = 'demodb', 
        sql = 'merge_stock_price.sql', 
        dag=dag, 
    )
   
    #email_task = EmailOperator(
    #    task_id='send_email', 
    #    to='gloriatt502@gmail.com', 
    #    subject='Stock Price is downloaded', 
    #    html_contents="""<h3>Email Test</h3>""",
    #    dag=dag  
    #)


    download_task >> save_to_mysql_task >> postgresql_task 
    #>> email_task

    # [END documentation]


# [END tutorial]
