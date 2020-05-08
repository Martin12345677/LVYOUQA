from py2neo import Graph, Node, Relationship
import math
import os
import jieba
import re
from gensim.models import word2vec
import numpy as np
from keras.layers import Embedding, Dense, Flatten, LSTM
from keras.utils.np_utils import to_categorical
from keras.models import Sequential
from keras import models

path = 'F:\大创\旅游路线\旅游问答\data'

graph = Graph(
    host='127.0.0.1',
    http_port=7474,
    user='neo4j',
    password='neo4j'
)


def get_distance(sx, sy, ex, ey):
    if not sx or not sy or not ex or not ey:
        return 0
    sx = float(sx)
    sy = float(sy)
    ex = float(ex)
    ey = float(ey)
    pio_dis = math.sqrt((sx-ex) ** 2 + (sy-ey) ** 2)
    return pio_dis * 100


def set_rel(graph, rel_name='NEAR', tag=''):
    scenes = list(graph.find('scenery'))
    num = 0
    for scene in scenes:
        num = num + 1
        print(tag + ':', num, ':', len(scenes))
        for _scene in scenes:
            if tag in _scene.get('tag', ''):
                distance = get_distance(scene['lng'], scene['lat'], _scene['lng'], _scene['lat'])
                if 0 < distance < 50:
                    s1 = graph.find_one('scenery', property_key='sid', property_value=scene['sid'])
                    s2 = graph.find_one('scenery', property_key='sid', property_value=_scene['sid'])
                    rel = Relationship(s1, rel_name, s2)
                    rel['distance'] = distance
                    rel['tag'] = tag
                    graph.create(rel)


def make_dic(label, weight, tag):

    f = open(os.path.join(path, 'new_dict.txt'), 'a', encoding='utf-8')
    entities = graph.find(label)
    for entity in entities:
        name = entity['name']
        name = name.replace('...', '').replace(' ', '')
        an = re.search(r'[(（].*[)）]', name)
        name = re.sub(r'[(（].*[)）]', '', name)
        name = re.sub(r'[(（].*', '', name)
        if an:
            an = an.group(0)
            f.write('*' + an[1: len(an)-1] + ' ' + str(weight) + ' ' + tag + '\n')
        f.write(name + ' ' + str(weight) + ' ' + tag + '\n')
        if entity['alias']:
            name = entity['alias']
            name = name.replace('...', '').replace(' ', '')
            an = re.search(r'[(（].*[)）]', name)
            print(name, an)
            name = re.sub(r'[(（].*[)）]', '', name)
            name = re.sub(r'[(（].*', '', name)
            if an:
                an = an.group(0)
                f.write('*' + an[1: len(an)-1] + ' ' + str(weight) + ' ' + tag + '\n')
            f.write(name + ' ' + str(weight) + ' ' + tag + '\n')
    f.close()


def make_words():
    sceneries = graph.find('scenery')
    sourse = ''
    for scene in sceneries:
        name = scene['name']
        intro = scene['intro'] or ''
        tag = scene['content_tag'] or ''
        alias = scene['alias'] or ''
        sourse += name + ' ' + intro + ' ' + tag + ' ' + alias

    sourse = re.sub(r'[\r\n]', '', sourse)
    jieba.load_userdict(os.path.join(path, 'dict.txt'))
    words = jieba.cut(sourse)

    f = open(os.path.join(path, 'words.txt'), 'a', encoding='utf-8')

    for word in words:
        if word not in [' ', '~', '`', '"', '?', '/', '	', '「', '」', '(', ')', '：', '——', '？', '-', '“', '”', '……',
                        '。',
                        '，', '：', '；', '？', '！', ':', '.', '!', '《', '》', '\'', '（', '）', '…', '￥', '[', ']', '、', ',']:
            f.write(word + ' ')
    f.close()


def make_vec():
    sentences = word2vec.Text8Corpus(os.path.join(path, 'words.txt'))

    model = word2vec.Word2Vec(sentences, sg=1, size=100, hs=100, min_count=1, window=3)
    model.save(os.path.join(path, 'word2vec.bin'))


def get_random_names(names, size):
    ns = []
    for i in np.random.choice(len(names), size):
        ns.append(names[i])
    return ns


def make_one_question_data(f, type, question, names, size):
    ns = get_random_names(names, size)
    last_name = ns[size-1]
    time = 0
    for n in ns:
        if '*' not in question:
            time = time + 1
        if time > 5:
            break
        q = question.replace('*', n).replace('#', last_name)
        last_name = n
        f.write(q + ' ' + str(type) + '\n')
        # print(question)


def make_data(fname, size):

    sceneries = graph.find('scenery')
    names = []
    for scenery in sceneries:
        names.append(scenery['new_name'].replace('...', '').replace(' ', ''))

    q = open(os.path.join(path, '问题模板.txt'), 'r', encoding='utf-8')
    f = open(os.path.join(path, fname), 'w', encoding='utf-8')
    questions = q.read().split('\n')
    for question in questions:
        question = question.split(' ')
        type = question[0]
        question = question[1]
        make_one_question_data(f, type, question, names, size)
    f.close()
    q.close()


def to_vec(sequences, word2idx, MAX_LENGTH = 20):
    results = np.zeros((len(sequences), MAX_LENGTH))
    for i, sequence in enumerate(sequences):
        sen = []
        for j in range(MAX_LENGTH):
            if j < len(sequence):
                word = sequence[j].encode('utf-8').decode('utf-8-sig')
                try:
                    sen.append(word2idx[word])
                except:
                    sen.append(0)
            else:
                sen.append(0)
        results[i] = sen
    return results


def make_model(val_num, model_name, epoch=20, MAX_LENGTH=20):

    embedding_model = word2vec.Word2Vec.load(os.path.join(path, 'word2vec.bin'))
    jieba.load_userdict(os.path.join(path, 'dict.txt'))

    f = open(os.path.join(path, 'train_data.txt'), 'r', encoding='utf-8')
    train_data = f.read()
    f.close()
    f = open(os.path.join(path, 'test_data.txt'), 'r', encoding='utf-8')
    test_data = f.read()
    f.close()

    word2idx = {}

    f = open(os.path.join(path, 'word2idx.txt'), 'w', encoding='utf-8')

    vocab_list = [(k, embedding_model.wv[k]) for k, v in embedding_model.wv.vocab.items()]

    embedding_matrix = np.zeros((len(embedding_model.wv.vocab.items()) + 1, embedding_model.vector_size))

    for i in range(len(vocab_list)):
        word = vocab_list[i][0]
        word2idx[word] = i + 1
        if i != 0:
            f.write('\n' + word + ' ' + str(i + 1))
        else:
            f.write(word + ' ' + str(i + 1))
        embedding_matrix[i + 1] = vocab_list[i][1]

    train_sentences = [sentence.split(' ')[0] for sentence in train_data.split('\n')]
    train_labels = [int(sentence.split(' ')[1].encode('utf-8').decode('utf-8-sig')) for sentence in
                    train_data.split('\n')]
    test_sentences = [sentence.split(' ')[0] for sentence in test_data.split('\n')]
    test_labels = [int(sentence.split(' ')[1].encode('utf-8').decode('utf-8-sig')) for sentence in
                   test_data.split('\n')]

    # 打乱数据
    indices = np.random.choice(len(train_sentences), len(train_sentences), replace=False)
    train_sentences = np.array(train_sentences)[indices]
    train_labels = np.array(train_labels)[indices]
    indices = np.random.choice(len(test_sentences), len(test_sentences), replace=False)
    test_sentences = np.array(test_sentences)[indices]
    test_labels = np.array(test_labels)[indices]

    train_labels = to_categorical(train_labels)
    test_labels = to_categorical(test_labels)

    train_words = [jieba.lcut(s) for s in train_sentences]
    test_words = [jieba.lcut(s) for s in test_sentences]

    train_x = to_vec(train_words, word2idx)
    test_x = to_vec(test_words, word2idx)

    val_x = test_x[:val_num]
    val_labels = test_labels[:val_num]
    test_x = test_x[val_num:]
    test_labels = test_labels[val_num:]

    model = Sequential()
    model.add(Embedding(105365, 100, input_length=MAX_LENGTH))
    model.add(Flatten())
    model.add(Dense(128, activation='relu'))
    model.add(Dense(20, activation='softmax'))
    model.layers[0].set_weights([embedding_matrix])
    model.layers[0].trainable = False

    model.summary()

    model.compile(optimizer='rmsprop',
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    history = model.fit(train_x,
                        train_labels,
                        epochs=epoch,
                        batch_size=512,
                        validation_data=(test_x, test_labels))

    model.save(os.path.join(path, model_name))


def set_name():
    f = open(os.path.join(path, 'old_dict.txt'), 'r', encoding='utf-8')
    dict = f.read()
    f.close()
    names = {}
    alias = {}
    f = open(os.path.join(path, 'new_dict.txt'), 'a', encoding='utf-8')
    num = 1
    for item in dict.split('\n'):
        parts = item.split(' ')
        if parts[2].startswith('ns'):
            print(num)
            num = num + 1
            sid = parts[2].replace('ns', '')
            node = graph.find_one('scenery', property_key='sid', property_value=sid)
            city = graph.match_one(start_node=node, rel_type='LOCATED_IN').end_node()['name']
            if city in parts[0] and '园' not in parts[0] and '馆' not in parts[0]:
                new_name = parts[0].replace(city, '')
            else:
                new_name = parts[0]
            name = names.get(sid, '')
            if not name:
                names[sid] = new_name
                node['new_name'] = new_name
            else:
                alias[sid] = new_name
                node['alias'] = new_name

            f.write(new_name + ' 2000 nss\n')
            graph.push(node)
    f.close()

    # num = 1
    # for sid in names:
    #     print('name:', num, ':', len(names))
    #     node = graph.find_one('scenery', property_key='sid', property_value=sid)
    #     node['new_name'] = names[sid]
    #     graph.push(node)
    #     num = num + 1
    # num = 1
    # for sid in alias:
    #     print('alias:', num, ':', len(names))
    #
    #     node = graph.find_one('scenery', property_key='sid', property_value=sid)
    #     node['alias'] = alias[sid]
    #     graph.push(node)
    #     num = num + 1

# make_dic('scenery', 2000, 'ns')
# make_dic('province', 1000, 'np')
# make_dic('city', 1500, 'nc')

# make_data('train_data.txt', 400)
# make_data('test_data.txt', 200)

# make_model(val_num=5000, model_name='first_dense_model.h5', epoch=10, MAX_LENGTH=20)

# set_rel(graph, rel_name='NEAR_FOOD', tag='美食')
# set_rel(graph, rel_name='NEAR_RELAX', tag='娱乐')
# set_rel(graph, rel_name='NEAR_NATURE', tag='风景')
# set_rel(graph, rel_name='NEAR_NATURE', tag='自然')
# set_rel(graph, rel_name='NEAR_PARK', tag='公园')
# set_rel(graph, rel_name='NEAR_PLAYGROUND', tag='游乐场')
# set_rel(graph, rel_name='NEAR_AQUARIUM', tag='水族馆')
# set_rel(graph, rel_name='NEAR_MUSEUM', tag='博物馆')
# set_rel(graph, rel_name='NEAR_HOLIDAY', tag='度假村')
# set_rel(graph, rel_name='NEAR_CULTURE', tag='文物')
# set_rel(graph, rel_name='NEAR_SEA', tag='海滨')
# set_rel(graph, rel_name='NEAR_SCIENCE', tag='科技')
# set_rel(graph, rel_name='NEAR_ZOO', tag='动物')

# make_vec()
# make_data('test_data.txt', 200)
# make_data('train_data.txt', 400)
# make_model(val_num=50, model_name='first_dense_model.h5', epoch=10)
