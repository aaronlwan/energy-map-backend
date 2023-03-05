import folium
import osmnx as ox
import geojson
import geopandas as gpd
from flask import request, jsonify
import requests
import pandas as pd
from flask_cors import CORS, cross_origin
import numpy as np

def mapRoutes(app):
    @app.route('/citytolatlon')
    @cross_origin()
    def cityToLatLon():
        args = request.args
        city = args.get("city")
        stateCode = args.get("stateCode")
        country = args.get("country")
        params = {'q': city + ',' + stateCode + ',' + country, 'appid':'fc5358fa54599e6cf8e27577d2fa0df8'}
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
        city = args.get("city")
        state = args.get("state")

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
            geometries = ox.geometries.geometries_from_point(loc, tags={"building": True}, dist=r)
            if "addr:postcode" not in geometries.columns: return (0, 0, 0)

            #map zip codes to pop density
            zip_density = pd.read_csv('zip_population.csv').set_index('ZIP')
            zip_density['urban'] = zip_density['pop_density'] >= 1000
            zip_density.to_csv('zip_population.csv')
                
            #default urban/rural truth value
            default = zip_density.loc[int(geometries['addr:postcode'].value_counts().index[0])]['urban']
            
            geometries = geometries.to_crs("EPSG:3857") #converting lat lon to m^2
            #geometries['building:levels'] = geometries['building:levels'].fillna(0).astype('int') #removing nans
            geometries["building:levels"] = pd.to_numeric(geometries["building:levels"], errors="coerce").dropna().astype("int")
            geometries['addr:postcode'] = pd.to_numeric(geometries['addr:postcode'].str[:5], errors="coerce").dropna().astype("int")
            # sunroof = pd.read_csv('project-sunroof-postal_code.csv').set_index('zip')
            sunroof = pd.read_csv('project-sunroof-city.csv')
            states = pd.read_csv('states.csv')
            fullName = states[states.code==state].iloc[0,0]
            row = sunroof[(sunroof["region_name"]==city) & (sunroof["state_name"]==fullName)].iloc[0]
            count_qualified, total_kwh_potential, existing_installs, median_kwh_potential = row["count_qualified"], row["kw_total"] * 8760, row["existing_installs_count"], row["kw_median"] * 8760

            btu_per_year = 0
            for i, row in geometries.iterrows():
                zip = row['addr:postcode']
                if pd.isna(zip):
                    if default: per_foot = 39200
                    else: per_foot = 35500
                else:
                    if zip_density.loc[int(zip)]['urban']: per_foot = 39200
                    else: per_foot = 35500

                energy = per_foot * row['geometry'].area * 10.7639 #m^2 to ft^2

                stories = row['building:levels']
                #stories = int(max([v for v in stories.split() if v.isdigit()]))
                if stories > 5: energy *= 201 / 114
                elif stories > 1: energy *= 1.024 ** stories
                btu_per_year += energy
                
            btu_per_hour = btu_per_year / 8760
            watts = btu_per_hour * 3.41214e+3
            kilowatts = watts / 1000
            kwh_per_year = kilowatts * 8760
            kwh_per_year

            return (kwh_per_year, count_qualified, total_kwh_potential, existing_installs, median_kwh_potential, len(geometries))


        def get_map(lat, lon, r, demand):
            loc = (lat, lon)
            roads_df = ox.geometries.geometries_from_point(loc, tags= {"highway": True}, dist=r)
            m = folium.Map(list(loc), zoom_start=16)
            folium.Circle(location=loc, radius=r, color="red", opacity=0.7, fill=True, fillOpacity=0.15).add_to(m)
            geometries = ox.geometries.geometries_from_point(loc, tags= {"landuse": ["landfill", "greenfield", "brownfield"], "building": "parking"}, dist=r)
            if "landuse" not in geometries.columns:
                return m._repr_html_(), 0, pd.Series()
            roads = []
            for shape in geometries[geometries["landuse"] != "parking"]['geometry']:
                road = roads_df.loc[shape.contains(roads_df["geometry"])]
                roads.append(road)

            roads = gpd.GeoDataFrame(pd.concat(roads, ignore_index=True))
            roads = roads[roads.geom_type == "LineString"]

            roads['geometry'] = roads['geometry'].buffer(0.0001)
            geometries = geometries.reset_index()
            geometries['solrad'] = geometries.apply(lambda x: solrad(x['geometry'].centroid.y, x['geometry'].centroid.x), axis=1)

            folium.GeoJson(data=geometries['geometry'], style_function=lambda _: {'fillOpacity': 0}).add_to(m)
            panels = gpd.overlay(geometries, roads, how='difference')
            panels = panels.explode()
            panels['Area'] = panels['geometry'].to_crs("EPSG:3857").area
            panels = panels[panels['Area'] > 250]

            panels['Production'] = panels['solrad'] * 365 * panels['Area'] * 0.2
            for _, panel in panels.iterrows():
                if list(panel['geometry'].interiors) != []: continue
                L = list(panel['geometry'].exterior.coords)
                
                popup = f"""<div style="font-size: 11pt; width: 280px; border-radius: 10px; background-color: rgba(255, 255, 255, 0.5);"><strong><u>Projections:</u></strong>
                    <br> <strong>{round(panel['Area'], 2)} m<sup>2</sup></strong> of space available for solar panels
                    <br> <strong>{round(panel['Production'], 2)} kWh</strong> of energy could be produced annually"""
                if panel['Production'] * 100 / demand > 1: popup += f"<br> <strong>{round(panel['Production'] * 100 / demand, 2)}%</strong> of local demand could be met"
                popup += "</div>"
                
                folium.vector_layers.Polygon(
                    locations=[(x, y) for (y, x) in L],
                    popup=popup,
                    color="red",
                    fill=True,
                    fillColor='red',
                    opacity=0,
                    fillOpacity=0.75).add_to(m)
                

            folium.TileLayer(tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr = 'Esri', name = 'Esri Satellite', overlay = False, control = True).add_to(m)
            #html, total production, categories
            #return (m._repr_html_(), panels["Production"].sum(), geometries["building"].value_counts(), geometries)
            #return (m, panels["Production"].sum(), geometries["building"].value_counts(), geometries)
            return (m, panels["Production"].sum(), len(geometries["geometry"]), geometries)
        
        def calc_power_dist(df, lat, lon, r):
            loc = (lat, lon)
            power = ox.geometries.geometries_from_point(loc, tags={"power": ["substation", "tower"]}, dist=r)
            power["centroid"] = power["geometry"].centroid
            df["centroid"] = df["geometry"].centroid
            df["power_dist"] = 0
            for i, row in df.iterrows():
                best = float("inf")
                for _, row2 in power.iterrows():
                    curr = row["centroid"].distance(row2.centroid)
                    if curr < best:
                        best = curr
                df.loc[i, "power_dist"] = best
            return df

        demand, count_qualified, total_kwh_potential, existing_installs, median_kwh_potential, number_buildings = get_demand(lat, lon, r)
        map, potential_production, number_sites, df = get_map(lat, lon, r, demand)
        distance_df = calc_power_dist(df, lat, lon, r)
        distance_df['Area'] = distance_df['geometry'].to_crs("EPSG:3857").area
        distance_df.sort_values(["Area", "power_dist"], ascending=[False, True])
        for i in range(int(len(distance_df) * 0.10)):
            best_lat, best_lon = distance_df.iloc[i]["centroid"].y, distance_df.iloc[i]["centroid"].x
            folium.Marker(location=[best_lat, best_lon], fill_color='red', radius=8).add_to(map)
        data = {"map_html": map._repr_html_(), "demand": demand, "existing_installs": existing_installs, "count_qualified": count_qualified, "total_kwh_potential": total_kwh_potential, "median_kwh_potential": median_kwh_potential,
                "number_buildings": number_buildings, "potential_production": potential_production, "number_sites": number_sites}
        json_data = jsonify(**data)
        return json_data