import connexion

app = connexion.FlaskApp(__name__, specification_dir='lineup_remote/')
app.add_api('lineup.yaml')
app.run(port=8080)
