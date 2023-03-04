import folium
import osmnx
import geojson
import geopandas
from flask import request
import jsonify

def mapRoutes(app):
    @app.route('/citytolatlon')
    def cityToLatLon():
        return "hello"
    @app.route('/latlontomap')
    def LatLontoMap():
        args = request.args
        lat = args.get("lat")
        lon = float(args.get("lon"))
        loc = (lat, lon)
        m = folium.Map(list(loc), zoom_start=17)
        geometries = osmnx.geometries.geometries_from_point(loc, tags={"building": True}, dist=1000)
        osmnx.geometries.geometries_from_place(lat, tags={"building": True}, dist=1000)
        folium.GeoJson(data=geometries['geometry']).add_to(m)
        map_file = m._repr_html_()
        return map_file