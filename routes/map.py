import folium
import osmnx
import geojson
import geopandas
from flask import request
import jsonify
import requests

def mapRoutes(app):
    @app.route('/citytolatlon')
    def cityToLatLon():
        args = request.args
        city = args.city
        stateCode = args.stateCode
        country = args.country
        params = {'q': city + ',' + stateCode + ',' + country, 'appid':'d7ecdfafc6f8d7054f83336651abe8fc'}
        response = requests.get(url='http://api.openweathermap.org/geo/1.0/direct', params=params)
        (lat, lon) = response.lat, response.lon
        return (lat, lon)
    @app.route('/latlontomap')
    def LatLontoMap():
        args = request.args
        lat = float(args.get("lat"))
        lon = float(args.get("lon"))
        loc = (lat, lon)
        m = folium.Map(list(loc), zoom_start=17)
        geometries = osmnx.geometries.geometries_from_point(loc, tags={"building": True}, dist=1000)
        folium.GeoJson(data=geometries['geometry']).add_to(m)
        map_file = m._repr_html_()
        return map_file