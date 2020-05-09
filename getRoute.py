from py2neo import Graph, Relationship
import math
import datetime
import setting
import re

graph = Graph(
    host=setting.GRAPH_HOST,
    http_port=setting.GRAPH_PORT,
    user=setting.GRAPH_USER,
    password=setting.GRAPH_PASSWORD
)


def get_all_cities():
    city_nodes = list(graph.find('city'))
    cities = []
    for node in city_nodes:
        start_node = graph.match_one(rel_type='LOCATED_IN', end_node=node).start_node()
        if not start_node['lat']:
            continue
        city = {
            'cid': node['cid'],
            'name': node['name'],
            'lat': start_node['lat'],
            'lng': start_node['lng']
        }
        # node['lat'] = float(start_node['lat'])
        # node['lng'] = float(start_node['lng'])
        # graph.push(node)
        cities.append(city)
    return cities


def get_distance(c1, c2):
    x1 = float(c1['lng'])
    y1 = float(c1['lat'])
    x2 = float(c2['lng'])
    y2 = float(c2['lat'])
    return 100 * math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def make_route():
    cities = get_all_cities()
    i = 0
    for begin in cities:
        d1 = {}
        d2 = {}
        min_path_1 = {}
        min_path_2 = {}
        used = {}
        for city in cities:
            d1[city['cid']] = 1000000
            d2[city['cid']] = 1000000
            used[city['cid']] = False
            min_path_1[city['cid']] = []
            min_path_2[city['cid']] = []
        d1[begin['cid']] = 0
        d2[begin['cid']] = 0

        while 1:
            v = -1
            for end in cities:
                if used[end['cid']]:
                    continue
                if v == -1 or d1[v['cid']] > d1[end['cid']]:
                    v = end

            if v == -1:
                break
            used[v['cid']] = True

            for end in cities:
                dis = get_distance(v, end)
                if 200 < dis or dis == 0:
                    continue
                end_cid = end['cid']
                end_d1 = d1[end_cid]
                end_d2 = d2[end_cid]
                new_d1 = d1[v['cid']] + dis
                path_1 = min_path_1[end_cid]
                if new_d1 < end_d1:
                    d2[end_cid] = end_d1
                    min_path_2[end_cid] = path_1
                    d1[end_cid] = new_d1
                    min_path_1[end_cid] = min_path_1[v['cid']] + [end['cid']]
                elif new_d1 < end_d2:
                    d2[end_cid] = new_d1
                    min_path_2[end_cid] = min_path_1[v['cid']] + [end['cid']]
        for end in cities:

            start_cid = begin['cid']
            end_cid = end['cid']
            add_route(
                start_cid=start_cid,
                dis1=d1[end_cid],
                path1=min_path_1[end_cid],
                dis2=d2[end_cid],
                path2=min_path_2[end_cid],
                end_cid=end_cid)
        i = i+1
        print(i, '/', len(cities))


def add_route(start_cid, dis1, path1, dis2, path2, end_cid):
    start_node = graph.find_one('city', property_key='cid', property_value=start_cid)
    end_node = graph.find_one('city', property_key='cid', property_value=end_cid)
    rel = Relationship(start_node, 'GUIDE_TO', end_node)
    rel['distance_1'] = dis1
    rel['route_1'] = path1
    rel['route_2'] = path2
    rel['distance_2'] = dis2
    graph.create(rel)


def get_day(begin_time, end_time):
    begin_time = datetime.datetime.strptime(begin_time, '%Y-%m-%dT%H:%M')
    end_time = datetime.datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
    return (end_time-begin_time).days


def print_max_property():
    scenes = list(graph.find(label='scenery'))
    rep = {
        'price': 0,
        'comment_num': 0,
        'rating': 0
    }
    for scene in scenes:
        prices = re.findall(r'\d+', scene.get('price', '0'))
        if len(prices) == 0:
            price = 0
        else:
            price = float(prices[0])
        try:
            rating = float(scene.get('rating', '0'))
        except:
            rating = 0
        if rating == 0:
            rating = 3
        try:
            comment_num = int(scene.get('comment_num', '0'))
        except:
            comment_num = 0
        if price > rep['price']:
            rep['price'] = price
        if rating > rep['rating']:
            rep['rating'] = rating
        if comment_num > rep['comment_num']:
            rep['comment_num'] = comment_num
    for key in rep:
        print(key, rep[key])


def get_score(city):
    return city['score']


def get_index(city):
    return city['index']


def set_city_score():
    cities = get_all_cities()
    sorted_cities = []
    for city in cities:
        c = graph.find_one(label='city', property_key='cid', property_value=city['cid'])
        scenes = [rel.start_node() for rel in list(graph.match(end_node=c, rel_type='LOCATED_IN'))]
        all_ratings = 0
        for scene in scenes:
            try:
                rating = float(scene.get('rating', 0))
                if not rating:
                    all_ratings += 3
                else:
                    all_ratings += rating
            except:
                all_ratings += 3
        num = len(scenes)
        score = num / 2 + all_ratings / num * 10
        c['score'] = score
        graph.push(c)
        sorted_cities.append(c)
    sorted_cities.sort(key=get_score, reverse=True)
    print(sorted_cities)


def get_n_city(route, n):
    rep = []
    for index, r in enumerate(route):
        city = graph.find_one(label='city', property_key='cid', property_value=r)
        city['index'] = index
        rep.append(city)
    rep.sort(key=get_score, reverse=True)
    rep = rep[0: n]
    rep.sort(key=get_index)
    return rep


def get_lng(elem):
    return float(elem.get('lng', 0))

# 15 30 20 35


def get_n_scenes(n, direction, city, prefer_tag, prefer_hot=0, prefer_discount=0, prefer_score=0):
    scenes = [rel.start_node() for rel in list(graph.match(rel_type='LOCATED_IN', end_node=city))]
    for index, scene in enumerate(scenes):
        is_prefer = 0
        # print(prefer_tag)
        for tag in prefer_tag:
            # print(tag)
            if tag in scene.get('tag', ''):
                is_prefer = 1
                break
        prices = re.findall(r'\d+', scene.get('price', '100'))
        if len(prices) == 0:
            price = 100
        else:
            price = float(prices[0])
        try:
            rating = float(scene.get('rating', '0'))
        except:
            rating = 0
        if rating == 0:
            rating = 3
        try:
            comment_num = int(scene.get('comment_num', '0'))
        except:
            comment_num = 0

        score = 10 + is_prefer * 5 + (15 + 15 * prefer_hot) * comment_num / 316.0 + (10 + 10 * prefer_discount) * (1 - price / 2998.0) + (20 + 15 * prefer_score) * rating / 5.0
        scenes[index]['score'] = score
        scenes[index]['hot'] = min(comment_num / 316.0 * 100 * 3, 100)
        scenes[index]['price'] = price
    scenes.sort(key=get_score, reverse=True)
    scenes = scenes[0: n]
    scenes.sort(key=get_lng, reverse=direction)
    return scenes


def get_route(begin_city, end_city, begin_time, end_time,
              prefer_tag, prefer_hot=0, prefer_discount=0, prefer_score=0):
    tag_dict = {
        '1': '博物馆',
        '2': '水族馆',
        '3': '风景区',
        '4': '动物园',
        '5': '文物古迹',
        '6': '公园',
        '7': '景点',
        '8': '休闲娱乐',
        '9': '体育场馆',
        '10': '游乐场',
        '11': '度假村',
        '12': '植物园',
        '13': '海滨浴场',
        '14': '科技馆'
    }
    prefer_tag = [tag_dict.get(tag, 'None') for tag in prefer_tag.split(':')]
    days = get_day(begin_time, end_time)
    begin_city = graph.find_one(label='city', property_key='name', property_value=begin_city)
    end_city = graph.find_one(label='city', property_key='name', property_value=end_city)
    direction = begin_city['lng'] > end_city['lng']
    if not begin_city or not end_city:
        return 0
    rel = graph.match_one(start_node=begin_city, rel_type='GUIDE_TO', end_node=end_city)
    route_1 = rel['route_1']
    route_2 = rel['route_2']
    routes = []
    if days >= len(route_1) + 1:
        route = [begin_city] + [graph.find_one(label='city', property_key='cid', property_value=cid) for cid in route_1]
        routes.append(route)
    else:
        routes.append([begin_city] + get_n_city(route_1, days - 1))
        routes.append(get_n_city(route_1, days))
    if route_1 != route_2:
        if days >= len(route_2) + 1:
            route = [begin_city] + [graph.find_one(label='city', property_key='cid', property_value=cid) for cid in route_2]
            routes.append(route)
        else:
            routes.append([begin_city] + get_n_city(route_2, days - 1))
            routes.append(get_n_city(route_2, days))
    scene_routes = []
    memory_scenes = {}
    for route in routes:
        all_price = 0
        all_score = 0
        if len(route) == days:
            scenes = []
            for index, city in enumerate(route):
                if city['cid'] in memory_scenes:
                    memory_ss = memory_scenes[city['cid']]
                    ss = memory_ss['scenes']
                    all_price += memory_ss['city_price']
                    all_score += memory_ss['city_score']
                else:
                    ss = []
                    city_score = 0
                    city_price = 0
                    for scene in get_n_scenes(2, direction, city, prefer_tag, prefer_hot, prefer_discount, prefer_score):
                        ss.append({
                            'sid': scene['sid'],
                            'name': scene['name'],
                            'img': scene['image'].split('<SPLIT>')[0],
                            'day': index + 1,
                            'tag': scene.get('tag', ''),
                            'type': scene.get('type', ''),
                            'location': {
                                'lat': scene.get('lat', 0),
                                'lng': scene.get('lng', 0)
                            },
                            'price': scene.get('price', ''),
                            'shop_hours': scene.get('shop_hours', ''),
                            'city': city['name'],
                            'overall_rating': scene.get('rating', 0),
                            'groupon_num': scene.get('groupon_num', 0),
                            'hot': scene.get('hot', 0)
                        })
                        all_price += scene.get('price', 0)
                        all_score += scene.get('score', 0)
                        city_score += scene.get('score', 0)
                        city_price += scene.get('price', 0)
                    memory_scenes[city['cid']] = {
                        'scenes': ss,
                        'city_score': city_score,
                        'city_price': city_price
                    }
                scenes += ss

        else:
            scenes = []
            all_city_score = 0
            for city in route:
                all_city_score += all_city_score + city['score']
            all_days = 0
            day = 1
            for index, city in enumerate(route):
                city_day = int(city['score'] / all_city_score * days)
                if index == len(route):
                    city_day = days - all_days
                all_days += city_day
                if city_day == 0:
                    continue
                ss = []
                for scene in get_n_scenes(2, direction, city, prefer_tag, prefer_hot, prefer_discount, prefer_score):
                    ss.append(scene)
                    all_price += scene.get('price', 0)
                    all_score += scene.get('score', 0)
                for i in range(city_day):
                    ss = [{
                        'sid': scene['sid'],
                        'name': scene['name'],
                        'img': scene['img'].split('<SPLIT>')[0],
                        'day': day,
                        'tag': scene.get('tag', ''),
                        'type': scene.get('type', ''),
                        'location': {
                            'lat': scene.get('lat', 0),
                            'lng': scene.get('lng', 0)
                        },
                        'price': scene.get('price', ''),
                        'shop_hours': scene.get('shop_hours', ''),
                        'city': city['name'],
                        'overall_rating': scene.get('rating', 0),
                        'groupon_num': scene.get('groupon_num', 0),
                        'hot': scene.get('hot', 0)
                    } for scene in ss[i * 2: i * 2 + 2]]
                    scenes += ss
                    day += 1
        scene_routes.append({
            'price': all_price,
            'time': days,
            'num': len(scenes),
            'img': scenes[0]['img'],
            'score': int(all_score),
            'scenes': scenes
        })
    scene_routes.sort(key=get_score, reverse=True)
    return {
        'code': 200,
        'routes': scene_routes
    }


# print(get_route(begin_city='北京',
#           end_city='洛阳',
#           begin_time='5-4-0',
#           end_time='5-7-0',
#           prefer_tag=''))
# get_all_cities()

# make_route()
#
#
# def add_score():
#     cities = get_all_cities()
#     for city in cities:
#         end_node = graph.find_one(label='city', property_key='cid', property_value=city['cid'])
#         rels = graph.match(rel_type='LOCATED_IN', end_node=end_node)
#         scenes = [rel.start_node() for rel in rels]
#
#         for scene in scenes:
