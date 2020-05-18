import json

from flask import Flask, render_template, request
from flask_mysqldb import MySQL

app = Flask(__name__)

app.config['MYSQL_HOST'] = ''
app.config['MYSQL_USER'] = ''
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = ''

mysql = MySQL(app)

@app.route('/')
def home():
    current_user = 0

    cur = mysql.connection.cursor()
    chosen_filters = request.args.to_dict(flat=False)

    if chosen_filters == {}:
        data = recommendations(current_user)
    else:

        cuisines_option_query = cuisines_option(chosen_filters)

        location_option_query = location_option(cuisines_option_query, chosen_filters)

        cur.execute(additional_options(location_option_query, chosen_filters))
        data = cur.fetchall()

    new_data = []
    for i in data:
        new_data.append(list(i))

    for i in new_data:
        i[6] = json.loads(i[6])
        i[15] = json.loads(i[15])

    return render_template('index.html', data=new_data)


def additional_options(query, filters):
    additional_filters = ['vegetarian', 'vegan', 'gluten_free', 'credit_card', 'takeaway']
    for filter_name in additional_filters:
        if filter_name in filters:
            query = "SELECT * FROM (%s) as t WHERE %s=1 " % (query, filter_name)
        else:
            query = "SELECT * FROM (%s) as t" % query

    return query


def cuisines_option(filters):
    query_fragment = """SELECT r.id, r.name, r.address, r.image, r.rating, r.price_range, r.timing,
                        r.vegan, r.vegetarian, r.gluten_free, r.credit_card, r.takeaway,
                        r.phone_num1, r.phone_num2, r.usual_menu_url, r.menu,
                        r.latitute, r.longitude, GROUP_CONCAT(c.name separator ', ') as cuisines
                        FROM restaurant r LEFT JOIN
                        restaurant_cuisine rc
                        ON rc.restaurant_id = r.id LEFT JOIN
                        cuisines c
                        ON c.id = rc.cuisine_id"""

    if 'cuisines' in filters:
        cuisines = tuple(filters.get('cuisines'))

        if len(cuisines) == 1:
            filtered_by_cuisine = ("%s WHERE c.name = '%s' GROUP BY r.id " % (query_fragment, cuisines[0]))

        else:
            filtered_by_cuisine = ("%s WHERE c.name in %s GROUP BY r.id " % (query_fragment, cuisines))

    else:
        filtered_by_cuisine = ("%s GROUP BY r.id " % query_fragment)

    return filtered_by_cuisine


def location_option(cuisine_query, filters):
    query_fragment = """id, name, address, image, rating, price_range, timing,
                vegan, vegetarian, gluten_free, credit_card, takeaway,
                phone_num1, phone_num2, usual_menu_url, menu, latitute,
                longitude"""

    if 'lat' and 'lon' in filters:

        lat = filters.get('lat')[0]
        lon = filters.get('lon')[0]

        formula = ("""(6371 * acos(cos( radians(%s
                )) * cos( radians( latitute )) * cos( radians( longitude ) - radians(%s
                ) ) + sin( radians(%s
                ) ) * sin( radians( latitute ))))""" % (lat, lon, lat))

        filter_by_distance = ("""SELECT %s, cuisines,
                   FORMAT(%s, 2) AS distance,
                   FORMAT((%s * 12), 1) AS time
                   FROM (%s) as t HAVING distance < 3 ORDER
                   BY distance""" % (query_fragment, formula, formula, cuisine_query))

    else:
        filter_by_distance = ("SELECT * FROM (%s) as t" % cuisine_query)

    return filter_by_distance


def recommendations(user_id):
    cur = mysql.connection.cursor()
    check_user = """SELECT EXISTS(SELECT user_id FROM restaurant_user WHERE user_id = %s)""" % user_id
    cur.execute(check_user)
    check_user_result = cur.fetchone()

    if check_user_result[0] == 0:
        top_restaurants_query = """SELECT r.id, r.name, r.address, r.image, r.rating, r.price_range, r.timing,
                                r.vegan, r.vegetarian, r.gluten_free, r.credit_card, r.takeaway,
                                r.phone_num1, r.phone_num2, r.usual_menu_url, r.menu,
                                r.latitute, r.longitude, GROUP_CONCAT(c.name separator ', ') as cuisines
                                FROM restaurant r LEFT JOIN
                                restaurant_cuisine rc ON rc.restaurant_id = r.id LEFT JOIN
                                cuisines c ON c.id = rc.cuisine_id  
                                GROUP BY r.id ORDER BY rating DESC"""

        cur.execute(top_restaurants_query)
        recommended_data = cur.fetchall()

    else:
        liked_restaurants = """SELECT restaurant_id FROM restaurant_user WHERE user_id = %s""" % user_id

        cuisines_query = """SELECT cuisines.name FROM restaurant_cuisine JOIN restaurant
        ON restaurant.id = restaurant_cuisine.restaurant_id JOIN cuisines
        ON cuisines.id = restaurant_cuisine.cuisine_id WHERE restaurant.id in (%s) 
        GROUP BY cuisines.name
        ORDER BY COUNT(*) DESC
        LIMIT 3""" % liked_restaurants

        cur.execute(cuisines_query)
        cuisines_result = cur.fetchall()

        liked_cuisines = []

        for tuple_cuisine in cuisines_result:
            for cuisine in tuple_cuisine:
                liked_cuisines.append(cuisine)
        liked_cuisines = tuple(liked_cuisines)

        other_filters_query = """SELECT vegan, vegetarian, gluten_free, price_range
                            FROM restaurant WHERE id in (%s) 
                            GROUP BY vegan, vegetarian, gluten_free, price_range
                            ORDER BY COUNT(*) DESC LIMIT 1""" % liked_restaurants

        cur.execute(other_filters_query)
        other_result = cur.fetchall()

        if len(liked_cuisines) == 1:
            recommended_restaurants = """SELECT r.id, r.name, r.address, r.image, r.rating, r.price_range, r.timing,
                                r.vegan, r.vegetarian, r.gluten_free, r.credit_card, r.takeaway,
                                r.phone_num1, r.phone_num2, r.usual_menu_url, r.menu,
                                GROUP_CONCAT(c.name separator ', ') as cuisines
                                FROM restaurant r LEFT JOIN
                                restaurant_cuisine rc
                                ON rc.restaurant_id = r.id LEFT JOIN
                                cuisines c
                                ON c.id = rc.cuisine_id
                                WHERE c.name = '%s' AND vegan = %s AND vegetarian = %s
                                AND gluten_free = %s AND price_range = %s
                                GROUP BY r.id 
                                """ % (liked_cuisines[0], other_result[0][0],
                                       other_result[0][1], other_result[0][2], other_result[0][3])
        else:
            recommended_restaurants = """SELECT r.id, r.name, r.address, r.image, r.rating, r.price_range, r.timing,
                                r.vegan, r.vegetarian, r.gluten_free, r.credit_card, r.takeaway,
                                r.phone_num1, r.phone_num2, r.usual_menu_url, r.menu,
                                GROUP_CONCAT(c.name separator ', ') as cuisines
                                FROM restaurant r LEFT JOIN
                                restaurant_cuisine rc
                                ON rc.restaurant_id = r.id LEFT JOIN
                                cuisines c
                                ON c.id = rc.cuisine_id
                                WHERE c.name in %s AND vegan = %s AND vegetarian = %s
                                AND gluten_free = %s AND price_range = %s
                                GROUP BY r.id 
                                """ % (liked_cuisines, other_result[0][0],
                                       other_result[0][1], other_result[0][2], other_result[0][3])
            cur.execute(recommended_restaurants)
        recommended_data = cur.fetchall()

    return recommended_data


if __name__ == "__main__":
    app.run()
