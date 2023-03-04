import folium
import osmnx
import geojson
import geopandas
from flask import request, jsonify
import requests
import pandas as pd
from flask_cors import CORS, cross_origin

def mapRoutes(app):
    @app.route('/citytolatlon')
    @cross_origin()
    def cityToLatLon():
        args = request.args
        city = args.get("city")
        stateCode = args.get("stateCode")
        country = args.get("country")
        params = {'q': city + ',' + stateCode + ',' + country, 'appid':'d7ecdfafc6f8d7054f83336651abe8fc'}
        response = requests.get(url='http://api.openweathermap.org/geo/1.0/direct', params=params)
        data = response.json()
        lat, lon = data[0]["lat"], data[0]["lon"]
        result = jsonify({"lat": lat, "lon": lon})
        return result
    @app.route('/latlontomap')
    @cross_origin()
    def LatLontoMap():
        args = request.args
        lat = float(args.get("lat"))
        lon = float(args.get("lon"))
        loc = (lat, lon)
        m = folium.Map(list(loc), zoom_start=17)
        geometries = osmnx.geometries.geometries_from_point(loc, tags={"building": True}, dist=1000)
        folium.GeoJson(data=geometries['geometry']).add_to(m)
        map_file = m._repr_html_()
        #making mapping of zip codes to population density
        zip_density = pd.read_csv('zip_population.csv').set_index('ZIP')
        zip_density['urban'] = zip_density['pop_density'] >= 1000
        zip_density.to_csv('zip_population.csv')
            
        #default urban/rural truth value
        default = zip_density.loc[int(geometries['addr:postcode'].value_counts().index[0])]['urban']

        btu_per_year = 0
        geometries = geometries.to_crs("EPSG:3857") #converting lat lon to square meters
        geometries['building:levels'] = geometries['building:levels'].fillna(0).astype('int') #removing nans
        for i, row in geometries.iterrows():
            zip = row['addr:postcode']
            if pd.isna(zip):
                if default: per_foot = 39200
                else: per_foot = 35500
            else:
                zip = int(zip[:5])
                if zip_density.loc[zip]['urban']:
                    per_foot = 39200
                else: 
                    per_foot = 35500

        energy = per_foot * row['geometry'].area * 10.7639 #m^2 to ft^2

        stories = row['building:levels']
        if stories > 5: energy *= 201 / 114
        elif stories > 1: energy *= 1.024 ** stories
        btu_per_year += energy
        btu_to_joules = btu_per_year * 1055.06
        joules_per_second = btu_to_joules / 31536000
        data = {"html": map_file, "demand": joules_per_second}
        json_data = jsonify(**data)
        return json_data