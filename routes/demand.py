import folium
import osmnx
import geojson
import geopandas
from flask import request, jsonify
import requests

def demandRoutes(app):
    @app.route('/latlontodemand')
    def LatLontoDemand():
        pass
    
    