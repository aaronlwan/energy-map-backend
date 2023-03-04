def mapRoutes(app):
    @app.route('/citytolatlon')
    def cityToLatLon():
        return "hello"