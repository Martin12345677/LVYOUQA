import web
import json
import getReply
import getRoute

urls = (
    '/reply', 'Reply',
    '/city', 'City',
    '/route', 'Route'
)


class Reply:

    def GET(self):
        return 0

    def POST(self):

        web.header('Access-Control-Allow-Origin', 'http://49.233.200.100:8001')
        web.header('content-type', 'json')
        web.header('Access-Control-Allow-Headers', 'content-type')
        print(web.data())
        data = json.loads(web.data().decode('utf-8'))
        sentence = data.get('sentence', '')
        lng = data.get('lng', '')
        lat = data.get('lat', '')

        rep = getReply.reply(sentence, lng, lat)
        return json.dumps(rep)

    def OPTIONS(self):
        web.header('Access-Control-Allow-Origin', 'http://49.233.200.100:8001')
        web.header('Access-Control-Max-Age', '2592000')
        web.header('content-type', 'json')
        web.header('Access-Control-Allow-Headers', 'content-type')
        return 100


class City:

    def GET(self):
        web.header('Access-Control-Allow-Origin', 'http://49.233.200.100:8001')
        web.header('content-type', 'json')
        web.header('Access-Control-Allow-Headers', 'content-type')
        province = web.input().get('province', '')
        res = {
            'data': {
                'cities': getReply.get_cities(province)
            }
        }
        return json.dumps(res)

    def OPTIONS(self):
        web.header('Access-Control-Allow-Origin', 'http://49.233.200.100:8001')
        web.header('Access-Control-Max-Age', '2592000')
        web.header('content-type', 'json')
        web.header('Access-Control-Allow-Headers', 'content-type')
        return 100


class Route:

    def GET(self):
        web.header('Access-Control-Allow-Origin', 'http://49.233.200.100:8001')
        web.header('content-type', 'json')
        web.header('Access-Control-Allow-Headers', 'content-type')

        begin_city = web.input().get('beginCity', '')
        end_city = web.input().get('endCity', '')
        begin_time = web.input().get('beginTime', '')
        end_time = web.input().get('endTime', '')
        prefer_tag = web.input().get('preferTag', '')
        prefer_hot = int(web.input().get('preferHot', 0))
        prefer_discount = int(web.input().get('preferDiscount', 0))
        prefer_score = int(web.input().get('preferScore', 0))

        if not begin_city or not end_city or not begin_time or not end_time:
            return 0

        return json.dumps(getRoute.get_route(
            begin_city=begin_city,
            end_city=end_city,
            begin_time=begin_time,
            end_time=end_time,
            prefer_tag=prefer_tag,
            prefer_hot=prefer_hot,
            prefer_discount=prefer_discount,
            prefer_score=prefer_score
        ))

    def OPTIONS(self):
        web.header('Access-Control-Allow-Origin', 'http://49.233.200.100:8001')
        web.header('Access-Control-Max-Age', '2592000')
        web.header('content-type', 'json')
        web.header('Access-Control-Allow-Headers', 'content-type')
        return 100

if __name__ == "__main__":
    app = web.application(urls, globals())

    app.run()

#
# app = web.application(urls, globals())
#
# application = app.wsgifunc()
