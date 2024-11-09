from flask import Flask, render_template
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

if __name__ == "__main__":
    app.run(debug=False)

# Home page
@app.route('/')
def homepage():
    return render_template('home.html')
