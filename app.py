from flask import Flask, render_template, request

import database as db

app = Flask(__name__)


@app.route("/")
def index():
    db.init_db()
    region = request.args.get("region") or None
    vacancies = db.get_approved_vacancies(region)
    return render_template(
        "index.html",
        vacancies=vacancies,
        regions=db.REGIONS,
        selected_region=region,
    )


if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
