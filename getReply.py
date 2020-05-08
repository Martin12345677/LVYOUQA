import json
from keras import models
import jieba
import jieba.posseg as pseg
import numpy as np
from py2neo import Graph
import datetime
import os
import math
import setting

path = os.path.join(os.path.dirname(__file__), 'data')


def get_word2idx():
    f = open(os.path.join(path, 'word2idx.txt'), 'r', encoding='utf-8')
    idx = f.read()
    f.close()
    idx = idx.split('\n')
    word2idx = {}
    for i in idx:
        word2idx[i.split(' ')[0].encode('utf-8').decode('utf-8-sig')] = int(i.split(' ')[1].encode('utf-8').decode('utf-8-sig'))
    return word2idx


def to_vec(sequences, MAX_LENGTH = 20):
    word2idx = get_word2idx()
    results = np.zeros((len(sequences), MAX_LENGTH))
    for i, sequence in enumerate(sequences):
        for j in range(MAX_LENGTH):
            if j < len(sequence):
                word = sequence[j].encode('utf-8').decode('utf-8-sig')
                try:
                    results[i, j] = word2idx[word]
                except:
                    results[i, j] = 0
            else:
                results[i, j] = 0
    return results


def predict(sentences):
    sentences = [jieba.lcut(sequence) for sequence in sentences]
    sentences = to_vec(sentences)
    model = models.load_model(os.path.join(path, 'first_dense_model.h5'))
    return model.predict(sentences)


def get_rating(elem):
    return elem.get('rating', '0')


def get_comment_num(elem):
    return elem.get('comment_num', '0')


def get_distance(elem):
    return elem['distance']


def get_name(sentence):
    words = pseg.cut(sentence)
    res = []
    for w, t in words:
        if t == 'np' or t == 'nc' or t == 'nss':
            res.append({'w': w, 't': t})
    return res


def get_place_distance(sx, sy, ex, ey):
    if not sx or not sy or not ex or not ey:
        return 0
    sx = float(sx)
    sy = float(sy)
    ex = float(ex)
    ey = float(ey)
    pio_dis = math.sqrt((sx-ex) ** 2 + (sy-ey) ** 2)
    return pio_dis * 100


def get_n_scene_by_distance(graph, n, lng, lat, label):
    scenes = graph.find('scenery')
    res = []
    for scene in scenes:
        if label in scene.get('tag', ''):
            distance = get_place_distance(lng, lat, scene['lng'], scene['lat'])
            if distance:
                res.append({
                    'name': scene['name'],
                    'sid': scene['sid'],
                    'distance': distance,
                    'tag': scene.get('tag', '暂无标签'),
                    'image': scene.get('image', '')
                })
    res.sort(key=get_distance)
    res = res[0:n]
    return res


def get_distance_from_rel(elem):
    return elem.relationships()[0]['distance']


def get_n_scene_by_distance_by_name(graph, n, name, rel_name):
    node = graph.find_one('scenery', property_key='new_name', property_value=name)
    if not node:
        node = graph.find_one('scenery', property_key='alias', property_value=name)
    rel = list(graph.match(rel_type=rel_name, start_node=node))
    rel.sort(key=get_distance_from_rel)
    rel = rel[0:n]
    res = []
    for r in rel:
        scene = r.end_node()
        res.append({
            'name': scene['name'],
            'sid': scene['sid'],
            'distance': r.relationships()[0]['distance'],
            'tag': scene.get('tag', '暂无标签'),
            'image': scene.get('image', '')
        })
    return res


# 获得某类别最近的n家景点
def get_near_scenes_by_type(graph, rel_name, tag, title, name1, local, n=5):
    if not name1:
        if not local:
            return {
                'reply': '暂时无法获取到您的位置，无法为您推荐附近的' + title + '。',
                'type': 0
            }
        else:
            return {
                'reply': get_n_scene_by_distance(graph, n, local['lng'], local['lat'], tag),
                'title': '为您推荐距离最近的' + str(n) + '家' + title,
                'type': 5
            }
    else:
        node = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node:
            node = graph.find_one('scenery', property_key='alias', property_value=name1)
        lng = node.get('lng', '')
        lat = node.get('lat', '')
        if not lng or not lat:
            return {
                'reply': '暂时无法定位该景点的位置，请到景点导航处查询。',
                'type': 0
            }
        else:
            res = get_n_scene_by_distance_by_name(graph, n, name1, rel_name)
            if len(res) == 0:
                return {
                    'reply': '该景点附近还没有' + title + '。',
                    'type': 0
                }
            return {
                'reply': res,
                'title': '为您推荐距离' + node['name'] + '最近的' + str(len(res)) + '家' + title,
                'type': 5
            }


def make_reply(tag, detail, local=None):

    print(detail)

    graph = Graph(
        host=setting.GRAPH_HOST,
        http_port=setting.GRAPH_PORT,
        user=setting.GRAPH_USER,
        password=setting.GRAPH_PASSWORD
    )
    name1 = ''
    name2 = ''
    city = ''
    province = ''
    if not detail and tag < 8:
        # 缺库处理
        return {
            'reply': '这个我还不太知道。',
            'type': 0
        }

    for d in detail:
        if d['t'] == 'nss':
            if not name1:
                name1 = d['w']
            else:
                name2 = d['w']
        elif d['t'] == 'np':
            province = d['w']
        elif d['t'] == 'nc':
            city = d['w']
        elif tag < 8:
            # 缺库处理
            return {
                'reply': '这个我还不太知道。',
                'type': 0
            }

    if tag == 0:
        if not name1:
            return {
                'reply': '这个景点我也没听说过，要不要换个关键词？',
                'type': 0
            }
        node = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node:
            node = graph.find_one('scenery', property_key='alias', property_value=name1)
        return {
            'reply': node.get('intro', '这个景点还没有介绍哦~'),
            'type': 0
        }

    elif tag == 1:
        if not name1:
            return {
                'reply': '这个景点我也没听说过，要不要换个关键词？',
                'type': 0
            }
        node = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node:
            node = graph.find_one('scenery', property_key='alias', property_value=name1)
        return {
            'reply': {
                'name': node['name'],
                'rating': node.get('rating', '暂无评分'),
                'sid': node['sid'],
                'comment_num': node.get('comment_num', '暂无人评价'),
                'tag': node.get('content_tag', '暂无标签'),
                'image': node.get('image', '')
            },
            'type': 1  # 返回评价页面
        }

    elif tag == 2:
        if not name1:
            return {
                'reply': '这个景点我也没听说过，要不要换个关键词？',
                'type': 0
            }
        node1 = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node1:
            node1 = graph.find_one('scenery', property_key='alias', property_value=name1)
        if name2:
            node2 = graph.find_one('scenery', property_key='new_name', property_value=name2)
            if not node2:
                node2 = graph.find_one('scenery', property_key='alias', property_value=name2)
            return {
                'reply': {
                    'p1': {
                        'name': name1,
                        'lat': node1['lat'],
                        'lng': node1['lng']
                    },
                    'p2': {
                        'name': name2,
                        'lat': node2['lat'],
                        'lng': node2['lng']
                    }
                },
                'type': 2  # 表示两个景点的导航
            }
        return {
            'reply': {
                'p1': {
                    'name': name1,
                    'lat': node1['lat'],
                    'lng': node1['lng']
                }
            },
            'type': 3  # 表示一个景点的导航
        }

    elif tag == 3:
        rel = []
        if city:
            node = graph.find_one('city', property_key='name', property_value=city)
            rel = list(graph.match(rel_type='LOCATED_IN', end_node=node))

        elif province:
            node1 = graph.find_one('province', property_key='name', property_value=province)
            rel2 = list(graph.match(rel_type='LOCATED_IN', end_node=node1))
            nodes = [r.start_node() for r in rel2]
            for node in nodes:
                rel.extend(list(graph.match(rel_type='LOCATED_IN', end_node=node)))
        else:
            return {
                'reply': '您是不是忘记说地点了？',
                'type': 0  # 表示本地推荐
            }
        scenes = [r.start_node() for r in rel]
        scenes.sort(key=get_comment_num, reverse=True)
        scenes = scenes[0:10]
        return {
            'title': '为您推荐' + (city or province) + '人气最高的十个景点',
            'reply': scenes,
            'type': 5  # 表示返回的是景点列表
        }

    elif tag == 4:
        if not name1:
            return {
                'reply': '这个景点我也没听说过，要不要换个关键词？',
                'type': 0
            }
        node = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node:
            node = graph.find_one('scenery', property_key='alias', property_value=name1)
        return {
            'reply': node.get('price', '这个景点还没有门票信息~'),
            'type': 0
        }

    elif tag == 5:
        if not name1:
            return {
                'reply': '这个景点我也没听说过，要不要换个关键词？',
                'type': 0
            }
        node = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node:
            node = graph.find_one('scenery', property_key='alias', property_value=name1)
        return {
            'reply': node.get('shop_hours', '这个景点还没有开放信息~'),
            'type': 0
        }

    elif tag == 6:
        if not name1:
            return {
                'reply': '这个景点我也没听说过，要不要换个关键词？',
                'type': 0
            }
        node = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node:
            node = graph.find_one('scenery', property_key='alias', property_value=name1)
        address = node.get('address', '')
        if address:
            return {
                'reply': {
                    'name': node['name'],
                    'address': node.get('address', '暂时没有该景点的位置信息'),
                    'lat': node.get('lat', -1),
                    'lng': node.get('lng', -1)
                },
                'type': 6  # 表示地图视图
            }
        else:
            return {
                'reply':  '暂时没有该景点的位置信息',
                'type': 0
            }

    elif tag == 7:
        if not name1:
            return {
                'reply': '这个景点我也没听说过，要不要换个关键词？',
                'type': 0
            }
        node = graph.find_one('scenery', property_key='new_name', property_value=name1)
        if not node:
            node = graph.find_one('scenery', property_key='alias', property_value=name1)
        return {
            'reply': {
                'name': node['name'],
                'intro': node.get('intro', ''),
                'image': node.get('image', ''),
                'sid': node['sid']
            },
            'type': 7  # 表示详细视图
        }

    elif tag == 8:
        return get_near_scenes_by_type(graph, rel_name='NEAR_FOOD', tag='美食', title='餐厅', name1=name1, local=local, n=5)

    elif tag == 9:
        return get_near_scenes_by_type(graph, rel_name='NEAR_RELAX', tag='娱乐', title='娱乐场所', name1=name1, local=local, n=5)

    elif tag == 10:
        return get_near_scenes_by_type(graph, rel_name='NEAR_NATURE', tag='风景', title='风景区', name1=name1, local=local, n=5)

    elif tag == 11:
        return get_near_scenes_by_type(graph, rel_name='NEAR_PARK', tag='公园', title='公园', name1=name1, local=local, n=5)

    elif tag == 12:
        return get_near_scenes_by_type(graph, rel_name='NEAR_PLAYGROUND', tag='游乐场', title='游乐场', name1=name1, local=local, n=5)

    elif tag == 13:
        return get_near_scenes_by_type(graph, rel_name='NEAR_AQUARIUM', tag='水族馆', title='水族馆', name1=name1, local=local, n=5)

    elif tag == 14:
        return get_near_scenes_by_type(graph, rel_name='NEAR_MUSEUM', tag='博物馆', title='博物馆', name1=name1, local=local, n=5)

    elif tag == 15:
        return get_near_scenes_by_type(graph, rel_name='NEAR_HOLIDAY', tag='度假', title='度假村', name1=name1, local=local, n=5)

    elif tag == 16:
        return get_near_scenes_by_type(graph, rel_name='NEAR_CULTURE', tag='文物', title='文物古迹', name1=name1, local=local, n=5)

    elif tag == 17:
        return get_near_scenes_by_type(graph, rel_name='NEAR_SEA', tag='海滨', title='海滨浴场', name1=name1, local=local, n=5)

    elif tag == 18:
        return get_near_scenes_by_type(graph, rel_name='NEAR_SCIENCE', tag='科技', title='科技馆', name1=name1, local=local, n=5)

    elif tag == 19:
        return get_near_scenes_by_type(graph, rel_name='NEAR_ZOO', tag='动物', title='动物园', name1=name1, local=local, n=5)


def reply(sentence, lng, lat):
    jieba.load_userdict(os.path.join(path, 'dict.txt'))
    if lng:
        local = {
            'lng': lng,
            'lat': lat
        }
    else:
        local = None
    tag = np.argmax(predict([sentence])[0])
    detail = get_name(sentence)
    rep = make_reply(tag, detail, local)
    time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = {
        'text': rep['reply'],
        'type': rep['type'],
        'title': rep.get('title', ''),
        'time': time,
        'send': False
    }
    rep = {
        'msg': msg
    }
    return rep


def get_cities(province):
    graph = Graph(
        host='127.0.0.1',
        http_port=7474,
        user='neo4j',
        password='neo4j'
    )
    province = graph.find_one('province', property_key='name', property_value=province)
    if not province:
        return []
    rel = list(graph.match(rel_type='LOCATED_IN', end_node=province))
    return [r.start_node()['name'] for r in rel]


d = [
    {
        'w': '天津',
        't': 'np'
    },
    {
        'w': '12',
        't': 'nss25588'
    },
    {
        'w': '13',
        't': 'nss2422'
    }
]

# print(make_reply(5, d))
# print(make_reply(6, d))
# print(make_reply(10, d))

#
# class Request:
#     POST = None,
#     method = ''
#
# request = Request()
# request.POST = {
#         'sentence': '嵩山附近有什么玩的'
#     }
# request.method = 'POST'
# reply(request)
