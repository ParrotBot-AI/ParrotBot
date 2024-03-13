import pprint
from datetime import datetime, timezone, timedelta, date
import numpy as np
from scipy.spatial.distance import cosine
from gensim.models import KeyedVectors
import time
import pandas as pd
from configs.environment import DATABASE_SELECTION
from sqlalchemy import null, select, union_all, and_, or_, join, outerjoin, update, insert
if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from blueprints.education.models import (
    VocabBase,
    VocabCategoryRelationships,
    VocabCategorys,
    VocabCategorySimilarities
)

def calculate_word_distance():
    # Original list of words without "animal"
    df = pd.read_csv("vocabs_new.csv")
    words_list = []
    df_c = pd.read_csv("Vocabs.csv")
    map = {}
    words_c = df_c['word'].values

    for index, row in df_c.iterrows():
        map[row['word']] = row['id']


    for index, row in df.iterrows():
        words_list.append(
            (index, row['word'], row['chinese'])
        )

    start = time.time()
    model_path = '/Users/zhilinhe/Desktop/GoogleNews-vectors-negative300.bin.gz'
    word_vectors = KeyedVectors.load_word2vec_format(model_path, binary=True)

    count = 0
    # List of words
    word_ids = []
    similarities = []
    c = []
    for input_tuple in words_list:
        input_id = input_tuple[0]
        input_word = input_tuple[1]
        input_c = input_tuple[2]
        r = {}
        for compare_word in words_c:
            if compare_word != input_id:
                try:
                    similarity = word_vectors.similarity(input_word, compare_word)
                    r[compare_word] = similarity
                except:
                    pass

        sorted_similarities = sorted(r.items(), key=lambda x: x[1], reverse=True)
        l = [str(map[str(word[0])]) for word in sorted_similarities[:10]]
        join_string = ';'.join(l)

        word_ids.append(input_word)
        similarities.append(join_string)
        c.append(input_c)
        if count % 50 == 0:
            print(count)
        count += 1

    df = pd.DataFrame({
        "word": word_ids,
        "similarity": similarities,
        "chinese":c
    })
    df.to_csv("simi.csv")

def insert_bd():
    with db_session('core') as session:
        df = pd.read_csv("simi.csv")
        df = df.drop_duplicates(subset='word')
        s_l = []
        s_r = []
        for index, row in df.iterrows():
            record = (
                session.query(VocabBase)
                .filter(VocabBase.word == row['word'])
                .one_or_none()
            )
            if record:
                new = {
                    "word_id": record.id,
                    "category_id": 3,
                    'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                    'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                }
                s_r.append(new)

                new = {
                    "word_id": record.id,
                    "similarities": row['similarity'] if (not pd.isnull(row['similarity'])) else None,
                    'create_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))),
                    'last_update_time': datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
                }
                s_l.append(new)

        session.execute(
            insert(VocabCategorySimilarities),
            s_l
        )
        session.execute(
            insert(VocabCategoryRelationships),
            s_r
        )

        try:
            session.commit()
            print("成功")
        except Exception as e:
            print("失败")



def condition():
    with open("场景词.txt", "r") as f:
        import re
        pattern = re.compile(r'([A-Za-z]+)\s*([\u4e00-\u9fff]+)')
        lines = f.readlines()
        eng, ch = [], []
        with db_session('core') as session:
            for line in lines:
                match = pattern.search(line)
                if match:
                    english, chinese = match.groups()
                else:
                    english, chinese = None, None

                if english:
                    record = (
                        session.query(VocabBase)
                        .filter(VocabBase.word == english.strip())
                        .one_or_none()
                    )
                    if not record:
                        print(english, chinese)
                        eng.append(english)
                        ch.append(chinese)

            print(len(eng))
            df = pd.DataFrame({
                "word":eng,
                "chinese":ch
            })
            df.to_csv("vocabs_new.csv")




if __name__ == "__main__":
    # condition()
    insert_bd()
