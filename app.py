from flask import Flask
from routes.map import mapRoutes
from flask_cors import CORS, cross_origin

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

@app.route('/')
@cross_origin()
def root():
    return "test"

mapRoutes(app)


if __name__ == '__main__':
    app.run()