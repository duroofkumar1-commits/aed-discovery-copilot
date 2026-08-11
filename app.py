from flask import Flask, send_from_directory

app = Flask(__name__, static_folder="web", static_url_path="/web")


@app.get("/")
def home():
    return send_from_directory("web", "index.html")


@app.get("/data/<path:filename>")
def data_file(filename):
    return send_from_directory("data", filename)
