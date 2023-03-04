from flask import Flask
from routes.map import mapRoutes

app = Flask(__name__)

@app.route('/')
def root():
    return "test"

mapRoutes(app)


if __name__ == '__main__':
    app.run()