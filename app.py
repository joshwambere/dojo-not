from flask import Flask
from DojoNotification import DojoNotification

app = Flask(__name__)

@app.route('/')
def bootstrap():
 Dojo = DojoNotification()
 return Dojo.index()

if __name__ == '__main__':
 app.run(debug=True)
    

