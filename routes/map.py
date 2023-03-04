import folium
import osmnx as ox
import geojson
import geopandas as gpd
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
        r = int(args.get("r"))

        def solrad(lat, lon):
            url = "https://developer.nrel.gov/api/pvwatts/v8.json"
            params = {"format" : "json",
                        "api_key": "Ni3ATnfSGPj3FkIRWZdSjwDQFfXGyZ3UprhmdB1k",
                        "system_capacity": 0.4,
                        "losses": 14,
                        "array_type": 0,
                        "module_type": 0,
                        "tilt": 0,
                        "azimuth": 0,
                        "lat": lat, "lon": lon}
            response = requests.get(url, params = params)
            return dict(response.json())['outputs']['solrad_annual']
        
        def get_demand(lat, lon, r):
            loc = (lat, lon)
            print(loc)
            #m = folium.Map(list(loc), zoom_start=17)
            geometries = ox.geometries.geometries_from_point(loc, tags={"building": True}, dist=r)
            #folium.GeoJson(data=geometries['geometry']).add_to(m)
            if len(geometries.columns) <= 1:
                return 0
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
            btu_per_year = 616547362576.184
            btu_per_hour = btu_per_year / 8760
            watts = btu_per_hour * 3.41214e+3
            kilowatts = watts / 1000
            kwh_per_year = kilowatts * 8760
            return kwh_per_year


        def get_map(lat, lon, r):
            loc = (lat, lon)
            print(loc)
            roads_df = ox.geometries.geometries_from_point(loc, tags= {"highway": True}, dist=r)
            m = folium.Map(list(loc), zoom_start=16)

            geometries = ox.geometries.geometries_from_point(loc, tags= {"landuse": ["landfill", "greenfield", "brownfield"], "building": "parking"}, dist=r)
            print(geometries.columns)
            print(geometries)
            if len(geometries.columns) <= 1:
                return m._repr_html_(), 0
            roads = []
            for shape in geometries[geometries["landuse"] != "parking"]['geometry']:
                road = roads_df.loc[shape.contains(roads_df["geometry"])]
            roads.append(road)

            roads = gpd.GeoDataFrame(pd.concat(roads, ignore_index=True))
            roads = roads[roads.geom_type == "LineString"]

            roads['geometry'] = roads['geometry'].buffer(0.0001)
            geometries = geometries.reset_index()
            geometries['solrad'] = geometries.apply(lambda x: solrad(x['geometry'].centroid.y, x['geometry'].centroid.x), axis=1)

            folium.GeoJson(data=geometries['geometry']).add_to(m)
            panels = gpd.overlay(geometries, roads, how='difference')
            panels = panels.explode()
            panels['Area'] = panels['geometry'].to_crs("EPSG:3857").area
            panels = panels[panels['Area'] > max(panels['Area'].quantile(0.25), 250)]

            panels['Production'] = panels['solrad'] * 365 * panels['Area'] * 0.2

            folium.GeoJson(data=panels, popup=folium.features.GeoJsonPopup(['Area', 'Production']), style_function=lambda x: {'fillColor': '#228B22', 'color': '#228B22'}).add_to(m)
            
            return (m._repr_html_(), panels["Production"].sum())

        demand = get_demand(lat, lon, r)
        map_html, production = get_map(lat, lon, r)
        data = {"map_html": map_html, "demand": demand, "production": production}
        json_data = jsonify(**data)
        return json_data