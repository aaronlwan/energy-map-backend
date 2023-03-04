from flask import Flask, request, jsonify
import folium
import osmnx

app = Flask(__name__)

@app.route('/')
def root():
    return "test"

if __name__ == '__main__':
    app.run()